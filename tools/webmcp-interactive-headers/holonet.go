package main

import (
	"context"
	"encoding/json"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"strings"
	"time"
	"unicode"
)

const holonetClientID = "chaldea-holonet-machine"
const holonetIssuer = origin + "/application/o/chaldea-holonet/"
const holonetJWKSURL = holonetIssuer + "jwks/"
const holonetResource = "https://media.mcp.ryzhkov.dev/mcp"
const holonetScope = "holonet.read"
const holonetUsername = "chaldea-laptop-holonet-interactive"
const holonetCredential = ".config/chaldea/authentik/holonet-interactive.app-password"
const holonetServer = "3c86e6d7ff6c4a3296522cdf03d22bb0"
const holonetUser = "54b7d36cef804d3c8478474553ed3a82"

var holonetClaimName = regexp.MustCompile("^[a-z][a-z0-9_]{0,63}$")
var holonetChecked = []string{"holonet_server", "holonet_libraries", "holonet_catalog_users",
	"holonet_history_users", "holonet_target_users", "holonet_actions", "holonet_namespace"}

// The new ordinary reader never reads the independent admission-bound preset's secret.
func holonetBinding(node string, uid int) error {
	if node != "omarchy-macbook-air-igor" || uid != 1001 {
		return denied
	}
	return nil
}

func holonetMode() {
	node, err := os.Hostname()
	if err != nil || holonetBinding(node, os.Getuid()) != nil {
		fail()
	}
	path, err := credentialPath(os.Getuid(), holonetCredential)
	if err != nil {
		fail()
	}
	// Reuse the existing guarded plain app-password reader, named for its first OV use.
	password, err := readOVCredential(path, os.Getuid())
	if err != nil {
		fail()
	}
	ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
	defer cancel()
	token, err := acquireHolonet(ctx, httpClient(), password, time.Now)
	if err != nil {
		fail()
	}
	emit(token)
}

func acquireHolonet(ctx context.Context, client *http.Client, password string, now func() time.Time) (string, error) {
	form := url.Values{"grant_type": {"client_credentials"}, "client_id": {holonetClientID},
		"username": {holonetUsername}, "password": {password}, "scope": {holonetScope}, "resource": {holonetResource}}
	start := now().Unix()
	data, err := response(ctx, client, "POST", tokenURL, strings.NewReader(form.Encode()), 32768)
	if err != nil {
		return "", denied
	}
	var result struct {
		AccessToken string          `json:"access_token"`
		TokenType   string          `json:"token_type"`
		ExpiresIn   int64           `json:"expires_in"`
		Scope       string          `json:"scope"`
		Refresh     json.RawMessage `json:"refresh_token"`
	}
	if strictJSON(data, &result) != nil || !strings.EqualFold(result.TokenType, "Bearer") ||
		result.ExpiresIn <= 30 || result.ExpiresIn > 300 || result.Scope != holonetScope || len(result.Refresh) != 0 {
		return "", denied
	}
	keys, err := response(ctx, client, "GET", holonetJWKSURL, nil, 65536)
	if err != nil || validateHolonet(result.AccessToken, keys, now().Unix(), start, result.ExpiresIn) != nil {
		return "", denied
	}
	return result.AccessToken, nil
}

func exactHolonetList(claims map[string]json.RawMessage, key string, want []string) bool {
	raw, ok := claims[key]
	if !ok || len(raw) == 0 || raw[0] != '[' {
		return false
	}
	var values []string
	if json.Unmarshal(raw, &values) != nil || len(values) != len(want) {
		return false
	}
	for i, v := range values {
		if v != want[i] {
			return false
		}
	}
	return true
}

// Verify the signature first, then the exact catalog-only HoloNet contract.
// There is no arbitrary endpoint, namespace, user, library or credential selector.
func validateHolonet(token string, keys []byte, now, start, expires int64) error {
	if len(token) > 12288 {
		return denied
	}
	header, claims, err := verifySigned(token, keys)
	if err != nil {
		return denied
	}
	var h map[string]json.RawMessage
	if strictJSON(header, &h) != nil {
		return denied
	}
	for name := range h {
		if name != "alg" && name != "kid" && name != "typ" {
			return denied
		}
	}
	var alg, kid string
	if !text(h["alg"], &alg) || alg != "RS256" || !text(h["kid"], &kid) || !ovKid.MatchString(kid) {
		return denied
	}
	if raw, ok := h["typ"]; ok {
		var typ string
		if !text(raw, &typ) || typ != "JWT" && typ != "at+jwt" {
			return denied
		}
	}
	var c map[string]json.RawMessage
	if strictJSON(claims, &c) != nil || len(c) > 32 {
		return denied
	}
	for name := range c {
		// Canonical ASCII names reject case/Unicode aliases such as ſcope.
		if !holonetClaimName.MatchString(name) {
			return denied
		}
		if strings.HasPrefix(name, "holonet_") {
			known := false
			for _, key := range holonetChecked {
				if name == key {
					known = true
				}
			}
			if !known {
				return denied
			}
		}
		if strings.HasPrefix(name, "ov_") || strings.HasPrefix(name, "ha_") || strings.HasPrefix(name, "homelab_") ||
			strings.HasPrefix(name, "jocasta_") || name == "webmcp_identity" || name == "grants" || name == "project" || name == "source" {
			return denied
		}
	}
	var iss, aud, azp, scope, sub, server, namespace string
	if !text(c["iss"], &iss) || iss != holonetIssuer || !text(c["aud"], &aud) || aud != holonetResource ||
		!text(c["azp"], &azp) || azp != holonetClientID || !text(c["scope"], &scope) || scope != holonetScope ||
		!text(c["sub"], &sub) || !subject(sub) || len(sub) > 256 ||
		!text(c["holonet_server"], &server) || server != holonetServer ||
		!text(c["holonet_namespace"], &namespace) || namespace != "movies-catalog" {
		return denied
	}
	for _, r := range sub {
		if unicode.IsControl(r) {
			return denied
		}
	}
	if !exactHolonetList(c, "holonet_libraries", []string{"3"}) ||
		!exactHolonetList(c, "holonet_catalog_users", []string{holonetUser}) ||
		!exactHolonetList(c, "holonet_history_users", []string{}) ||
		!exactHolonetList(c, "holonet_target_users", []string{}) ||
		!exactHolonetList(c, "holonet_actions", []string{"catalog.read"}) {
		return denied
	}
	var iat, exp int64
	if !integer(c["iat"], &iat) || !integer(c["exp"], &exp) {
		return denied
	}
	if raw, ok := c["nbf"]; ok {
		var nbf int64
		if !integer(raw, &nbf) || nbf > now {
			return denied
		}
	}
	if iat <= 0 || iat > now+5 || iat < start-5 || exp <= now+30 || exp > now+300 ||
		exp-iat <= 0 || exp-iat > 300 || exp > start+expires+5 {
		return denied
	}
	return nil
}
