package main

import (
	"context"
	"encoding/json"
	"net/http"
	"net/url"
	"os"
	"slices"
	"strings"
	"time"
)

const shizuneClientID = "shizune-mcp-machine"
const shizuneIssuer = origin + "/application/o/shizune-mcp/"
const shizuneJWKSURL = shizuneIssuer + "jwks/"
const shizuneResource = "https://shizune.mcp.ryzhkov.dev/mcp"
const shizuneScope = "shizune.use"
const shizuneCredential = ".config/chaldea/authentik/shizune-interactive.app-password"

// Scope membership confers no authority beyond the signed fixed owner.
func shizuneScopes(scope string) bool { return slices.Contains(strings.Fields(scope), shizuneScope) }

func shizuneMode(host string) {
	node, err := os.Hostname()
	if err != nil || ovFullBinding(host, node, os.Getuid()) != nil {
		fail()
	}
	path, err := credentialPath(os.Getuid(), shizuneCredential)
	if err != nil {
		fail()
	}
	password, err := readOVCredential(path, os.Getuid())
	if err != nil {
		fail()
	}
	ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
	defer cancel()
	token, err := acquireShizune(ctx, httpClient(), host, password, time.Now)
	if err != nil {
		fail()
	}
	emit(token)
}

func acquireShizune(ctx context.Context, client *http.Client, host, password string, now func() time.Time) (string, error) {
	if _, ok := ovFullHosts[host]; !ok {
		return "", denied
	}
	username := "chaldea-" + host + "-shizune-interactive"
	scope := shizuneScope
	// The Shizune provider fixes the audience; no resource selector is sent.
	form := url.Values{"grant_type": {"client_credentials"}, "client_id": {shizuneClientID}, "username": {identityUsername(username)},
		"password": {password}, "scope": {scope}}
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
	if strictJSON(data, &result) != nil || !strings.EqualFold(result.TokenType, "Bearer") || result.ExpiresIn <= 30 || result.ExpiresIn > 300 || !shizuneScopes(result.Scope) || len(result.Refresh) != 0 {
		return "", denied
	}
	keys, err := response(ctx, client, "GET", shizuneJWKSURL, nil, 65536)
	if err != nil {
		return "", denied
	}
	if validateShizune(result.AccessToken, keys, now().Unix(), start, result.ExpiresIn) != nil {
		return "", denied
	}
	return result.AccessToken, nil
}

func validateShizune(token string, keys []byte, now, start, expires int64) error {
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
		if !text(raw, &typ) || (typ != "JWT" && typ != "at+jwt") {
			return denied
		}
	}
	var c map[string]json.RawMessage
	if strictJSON(claims, &c) != nil || len(c) > 32 {
		return denied
	}
	// Exact names only: a case-folded alias of a checked claim is ambiguous.
	for name := range c {
		lower := strings.ToLower(name)
		if !holonetClaimName.MatchString(name) || strings.HasPrefix(lower, "holonet_") || strings.HasPrefix(lower, "ov_") || strings.HasPrefix(lower, "jocasta_") || strings.HasPrefix(lower, "ha_") || strings.HasPrefix(lower, "homelab_") || (strings.HasPrefix(lower, "shizune_") && name != "shizune_owner") || slices.Contains(ovForeign, lower) {
			return denied
		}
	}
	var iss, aud, azp, scope, sub string
	if !text(c["iss"], &iss) || iss != shizuneIssuer || !text(c["aud"], &aud) || aud != shizuneResource ||
		!text(c["azp"], &azp) || azp != shizuneClientID || !text(c["scope"], &scope) || !shizuneScopes(scope) ||
		!text(c["sub"], &sub) || !subject(sub) {
		return denied
	}
	var owner string
	if !text(c["shizune_owner"], &owner) || owner != "igor" {
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
	if iat <= 0 || iat > now+5 || exp-iat <= 0 || exp-iat > 300 || exp-now <= 30 || exp-now > 300 || iat < start-5 || exp > start+expires+5 {
		return denied
	}
	return nil
}
