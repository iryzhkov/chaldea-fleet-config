// webmcp-interactive-headers is a closed, uncached native headers helper.
// Trust: system HTTPS roots at fixed issuer/JWKS endpoints, then RS256 verification.
// No CLI/config option can select another endpoint, resource, scope or client.
// The only invocations are the fixed tuples "jocasta HOST", "ov laptop" and
// "ov-full HOST" for laptop and omarchy-pc, plus "holonet laptop".
package main

import (
	"bytes"
	"context"
	"crypto"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math/big"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/user"
	"path/filepath"
	"regexp"
	"slices"
	"strconv"
	"strings"
	"syscall"
	"time"
	"unicode/utf8"
)

const origin = "https://auth.ryzhkov.dev"
const clientID = "jocasta-managed-interactive"
const issuer = origin + "/application/o/" + clientID + "/"
const resource = "https://jocasta.mcp.ryzhkov.dev/mcp"
const scopes = "jocasta.read jocasta.write"
const tokenURL = origin + "/application/o/token/"
const jwksURL = issuer + "jwks/"

// The OV mode uses the existing owned OV application in homelab-infra
// (playbooks/vars/authentik-ov-http-identities.yml) and the laptop's separate
// ordinary interactive account. It never reads the limited Chaldea preset's
// ov-tooling-codex credential. The verifier contract is ov-mcp ov_http/auth.py.
const ovClientID = "ov-http-a63e197f-machine"
const ovIssuer = origin + "/application/o/ov-http-a63e197f/"
const ovJWKSURL = ovIssuer + "jwks/"
const ovResource = "https://ov.mcp.ryzhkov.dev/mcp"
const ovScope = "ov.read"
const ovUsername = "chaldea-laptop-ov-interactive-codex"
const ovCredential = ".config/chaldea/authentik/ov-interactive-codex.app-password"
const ovNamespace = "viking://resources/homeassistant-api/rest-api.md"

// The full interactive OV mode uses the same owned OV provider and one
// resource-root account per selected host, whose signed grant carries all four
// actions (homelab-infra playbooks/vars/authentik-ov-http-full-interactive.yml).
// Ordinary Codex and Claude on that host share it. It never reads the narrow
// interactive or limited preset credentials, and they never read its file.
const ovFullScopes = "ov.read ov.write ov.remove ov.maintain"
const ovFullCredential = ".config/chaldea/authentik/ov-full-interactive.app-password"
const ovFullNamespace = "viking://resources"

var ovFullActions = []string{"read", "write", "remove", "maintain"}

// Each selected host's actual node name and numeric UID: homelab-infra binds
// the credential delivery to exactly these.
var ovFullHosts = map[string]struct {
	node string
	uid  int
}{"laptop": {"omarchy-macbook-air-igor", 1001}, "omarchy-pc": {"omarchy-pc", 1000}}

var denied = errors.New("managed headers unavailable")
var hosts = map[string]bool{"laptop": true, "agent-a": true, "agent-b": true, "omarchy-pc": true}
var ovKid = regexp.MustCompile(`^[A-Za-z0-9_.-]{1,128}$`)

// Claims a signed OV token must not carry: other services' grants and the
// managed Jocasta identity claims. Matching is on the lowercased name.
var ovForeign = []string{"jocasta_projects", "jocasta_operator", "webmcp_identity", "grants", "project",
	"source", "homelab_services", "homelab_hosts", "ha_entities", "ha_actions"}
var ovChecked = []string{"iss", "sub", "aud", "azp", "scope", "iat", "exp", "nbf", "ov_namespaces", "ov_actions"}

// ovContract is one closed OV mode's signed grant. A nil actions list means
// the token must carry no ov_actions claim at all.
type ovContract struct {
	scope     func(string) bool
	namespace string
	actions   []string
}

var ovNarrow = ovContract{scope: func(s string) bool { return s == ovScope }, namespace: ovNamespace}
var ovFull = ovContract{scope: exactOVFullScopes, namespace: ovFullNamespace, actions: ovFullActions}

type enrollment struct {
	Version    int    `json:"version"`
	Host       string `json:"host"`
	Username   string `json:"username"`
	Password   string `json:"password"`
	Generation int    `json:"generation"`
	Owner      string `json:"owner"`
}

func main() {
	switch selectMode(os.Args[1:]) {
	case "jocasta":
		jocasta(os.Args[2])
	case "ov":
		ov()
	case "ov-full":
		ovFullMode(os.Args[2])
	case "holonet":
		holonetMode()
	default:
		fail()
	}
}

// selectMode admits only the exact closed argument tuples.
func selectMode(args []string) string {
	if len(args) != 2 {
		return ""
	}
	if args[0] == "jocasta" && hosts[args[1]] {
		return "jocasta"
	}
	if args[0] == "holonet" && args[1] == "laptop" {
		return "holonet"
	}
	if args[0] == "ov" && args[1] == "laptop" {
		return "ov"
	}
	if _, ok := ovFullHosts[args[1]]; ok && args[0] == "ov-full" {
		return "ov-full"
	}
	return ""
}

func jocasta(host string) {
	current, err := user.Current()
	if err != nil {
		fail()
	}
	entry, err := readEnrollment(filepath.Join(current.HomeDir, ".config/webmcp-interactive/enrollment.json"), os.Getuid(), host)
	if err != nil {
		fail()
	}
	ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
	defer cancel()
	token, err := acquire(ctx, httpClient(), entry, time.Now)
	if err != nil {
		fail()
	}
	emit(token)
}

func ov() {
	path, err := ovCredentialPath(os.Getuid())
	if err != nil {
		fail()
	}
	password, err := readOVCredential(path, os.Getuid())
	if err != nil {
		fail()
	}
	ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
	defer cancel()
	token, err := acquireOV(ctx, httpClient(), password, time.Now)
	if err != nil {
		fail()
	}
	emit(token)
}

func ovFullMode(host string) {
	node, err := os.Hostname()
	if err != nil || ovFullBinding(host, node, os.Getuid()) != nil {
		fail()
	}
	path, err := credentialPath(os.Getuid(), ovFullCredential)
	if err != nil {
		fail()
	}
	password, err := readOVCredential(path, os.Getuid())
	if err != nil {
		fail()
	}
	ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
	defer cancel()
	token, err := acquireOVFull(ctx, httpClient(), host, password, time.Now)
	if err != nil {
		fail()
	}
	emit(token)
}

// ovFullBinding admits only the selected host's own machine and account: the
// kernel node name and real UID, never an argument, HOME or another variable.
func ovFullBinding(host, node string, uid int) error {
	binding, ok := ovFullHosts[host]
	if !ok || node != binding.node || uid != binding.uid {
		return denied
	}
	return nil
}

// This pipe is the only token output; no file or persistent token cache.
func emit(token string) {
	if json.NewEncoder(os.Stdout).Encode(map[string]string{"Authorization": "Bearer " + token}) != nil {
		os.Exit(1)
	}
}

func fail() {
	fmt.Fprintln(os.Stderr, denied.Error())
	os.Exit(1)
}

// Hold each directory FD through openat. No ancestor or leaf symlink is followed.
// Root/this UID may own ancestors; only this UID may own the private leaf.
func readPrivate(path string, uid int, limit int64) ([]byte, error) {
	if !filepath.IsAbs(path) || filepath.Clean(path) != path {
		return nil, denied
	}
	fd, err := syscall.Open("/", syscall.O_RDONLY|syscall.O_DIRECTORY|syscall.O_CLOEXEC, 0)
	if err != nil {
		return nil, denied
	}
	defer func() { syscall.Close(fd) }()
	parts := strings.Split(strings.TrimPrefix(path, "/"), "/")
	for _, part := range parts[:len(parts)-1] {
		var st syscall.Stat_t
		if syscall.Fstat(fd, &st) != nil || st.Mode&0022 != 0 || (st.Uid != 0 && int(st.Uid) != uid) {
			return nil, denied
		}
		next, e := syscall.Openat(fd, part, syscall.O_RDONLY|syscall.O_DIRECTORY|syscall.O_NOFOLLOW|syscall.O_CLOEXEC, 0)
		if e != nil {
			return nil, denied
		}
		syscall.Close(fd)
		fd = next
	}
	var parent syscall.Stat_t
	if syscall.Fstat(fd, &parent) != nil || int(parent.Uid) != uid || parent.Mode&0077 != 0 {
		return nil, denied
	}
	leaf, err := syscall.Openat(fd, parts[len(parts)-1], syscall.O_RDONLY|syscall.O_NOFOLLOW|syscall.O_NONBLOCK|syscall.O_CLOEXEC, 0)
	if err != nil {
		return nil, denied
	}
	file := os.NewFile(uintptr(leaf), "credential")
	defer file.Close()
	info, err := file.Stat()
	if err != nil {
		return nil, denied
	}
	st, ok := info.Sys().(*syscall.Stat_t)
	if !ok || !info.Mode().IsRegular() || info.Mode().Perm() != 0600 || int(st.Uid) != uid || st.Nlink != 1 || info.Size() < 1 || info.Size() > limit {
		return nil, denied
	}
	data, err := io.ReadAll(io.LimitReader(file, limit+1))
	if err != nil || int64(len(data)) > limit {
		return nil, denied
	}
	after, e := file.Stat()
	if e != nil || after.Size() != info.Size() || !after.ModTime().Equal(info.ModTime()) {
		return nil, denied
	}
	return data, nil
}

func readEnrollment(path string, uid int, host string) (enrollment, error) {
	var out enrollment
	if !hosts[host] {
		return out, denied
	}
	data, err := readPrivate(path, uid, 4096)
	if err != nil || strictJSON(data, &out) != nil {
		return enrollment{}, denied
	}
	if out.Version != 1 || out.Host != host || out.Username != "webmcp-interactive-"+host || out.Generation < 1 || out.Generation > 1000 || len(out.Owner) != 36 || len(out.Password) < 16 || len(out.Password) > 256 {
		return enrollment{}, denied
	}
	for _, b := range []byte(out.Password) {
		if b < 33 || b > 126 {
			return enrollment{}, denied
		}
	}
	return out, nil
}

// ovCredentialPath uses the account database's home for this UID. HOME, USER
// and every other environment value are ignored.
func ovCredentialPath(uid int) (string, error) {
	return credentialPath(uid, ovCredential)
}

func credentialPath(uid int, relative string) (string, error) {
	account, err := user.LookupId(strconv.Itoa(uid))
	if err != nil || account.Uid != strconv.Itoa(uid) || !filepath.IsAbs(account.HomeDir) || filepath.Clean(account.HomeDir) != account.HomeDir {
		return "", denied
	}
	return filepath.Join(account.HomeDir, relative), nil
}

// The infra role delivers the exact app password, without a newline.
func readOVCredential(path string, uid int) (string, error) {
	data, err := readPrivate(path, uid, 256)
	if err != nil || len(data) < 16 {
		return "", denied
	}
	for _, b := range data {
		if b < 33 || b > 126 {
			return "", denied
		}
	}
	return string(data), nil
}

// Reject duplicate JSON names, including in nested objects. Go's ordinary decoder
// would otherwise silently select the last occurrence of a security claim.
func strictJSON(data []byte, out any) error {
	dec := json.NewDecoder(bytes.NewReader(data))
	var value func() error
	value = func() error {
		t, e := dec.Token()
		if e != nil {
			return denied
		}
		if delim, ok := t.(json.Delim); ok {
			switch delim {
			case '{':
				seen := map[string]bool{}
				for dec.More() {
					key, e := dec.Token()
					if e != nil {
						return denied
					}
					name, ok := key.(string)
					if !ok || seen[name] {
						return denied
					}
					seen[name] = true
					if value() != nil {
						return denied
					}
				}
				end, e := dec.Token()
				if e != nil || end != json.Delim('}') {
					return denied
				}
			case '[':
				for dec.More() {
					if value() != nil {
						return denied
					}
				}
				end, e := dec.Token()
				if e != nil || end != json.Delim(']') {
					return denied
				}
			default:
				return denied
			}
		}
		return nil
	}
	if value() != nil {
		return denied
	}
	if _, e := dec.Token(); e != io.EOF {
		return denied
	}
	return json.Unmarshal(data, out)
}

func httpClient() *http.Client {
	return &http.Client{
		Timeout: 8 * time.Second,
		Transport: &http.Transport{Proxy: nil, DialContext: (&net.Dialer{Timeout: 3 * time.Second}).DialContext,
			TLSHandshakeTimeout: 3 * time.Second, ResponseHeaderTimeout: 4 * time.Second, MaxResponseHeaderBytes: 8192,
			DisableKeepAlives: true},
		CheckRedirect: func(*http.Request, []*http.Request) error { return denied },
	}
}

func response(ctx context.Context, client *http.Client, method, endpoint string, body io.Reader, limit int64) ([]byte, error) {
	req, err := http.NewRequestWithContext(ctx, method, endpoint, body)
	if err != nil {
		return nil, denied
	}
	req.Header.Set("Accept", "application/json")
	if method == "POST" {
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	}
	res, err := client.Do(req)
	if err != nil {
		return nil, denied
	}
	defer res.Body.Close()
	// Never read or report an error response, redirect target, or credential echo.
	if res.StatusCode != 200 {
		return nil, denied
	}
	data, err := io.ReadAll(io.LimitReader(res.Body, limit+1))
	if err != nil || int64(len(data)) > limit {
		return nil, denied
	}
	return data, nil
}

func acquire(ctx context.Context, client *http.Client, entry enrollment, now func() time.Time) (string, error) {
	form := url.Values{"grant_type": {"client_credentials"}, "client_id": {clientID}, "username": {entry.Username},
		"password": {entry.Password}, "scope": {scopes}, "resource": {resource}}
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
	if strictJSON(data, &result) != nil || !strings.EqualFold(result.TokenType, "Bearer") || result.ExpiresIn <= 30 || result.ExpiresIn > 300 || !exactScopes(result.Scope) || len(result.Refresh) != 0 {
		return "", denied
	}
	keys, err := response(ctx, client, "GET", jwksURL, nil, 65536)
	if err != nil {
		return "", denied
	}
	if validateToken(result.AccessToken, keys, entry.Username, now().Unix(), start, result.ExpiresIn) != nil {
		return "", denied
	}
	return result.AccessToken, nil
}

func exactScopes(s string) bool {
	f := strings.Fields(s)
	return len(f) == 2 && ((f[0] == "jocasta.read" && f[1] == "jocasta.write") || (f[1] == "jocasta.read" && f[0] == "jocasta.write"))
}

// exactOVFullScopes admits exactly the four OV families once each, in any
// order, separated by single spaces.
func exactOVFullScopes(s string) bool {
	got := strings.Split(s, " ")
	want := strings.Split(ovFullScopes, " ")
	slices.Sort(got)
	slices.Sort(want)
	return slices.Equal(got, want)
}

func acquireOV(ctx context.Context, client *http.Client, password string, now func() time.Time) (string, error) {
	return exchangeOV(ctx, client, ovUsername, password, ovScope, ovNarrow, now)
}

func acquireOVFull(ctx context.Context, client *http.Client, host, password string, now func() time.Time) (string, error) {
	if _, ok := ovFullHosts[host]; !ok {
		return "", denied
	}
	return exchangeOV(ctx, client, "chaldea-"+host+"-ov-full-interactive", password, ovFullScopes, ovFull, now)
}

func exchangeOV(ctx context.Context, client *http.Client, username, password, scope string, contract ovContract, now func() time.Time) (string, error) {
	// The established OV client exchange (Chaldea's session credential): no
	// resource indicator, since the provider's scope mapping fixes the audience.
	form := url.Values{"grant_type": {"client_credentials"}, "client_id": {ovClientID}, "username": {username},
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
	if strictJSON(data, &result) != nil || !strings.EqualFold(result.TokenType, "Bearer") || result.ExpiresIn <= 30 || result.ExpiresIn > 300 || !contract.scope(result.Scope) || len(result.Refresh) != 0 {
		return "", denied
	}
	keys, err := response(ctx, client, "GET", ovJWKSURL, nil, 65536)
	if err != nil {
		return "", denied
	}
	if validateOVContract(result.AccessToken, keys, now().Unix(), start, result.ExpiresIn, contract) != nil {
		return "", denied
	}
	return result.AccessToken, nil
}

// verifySigned checks the compact form, the RS256 header and the signature with
// the one matching RSA key from the pinned JWKS, then returns the verified
// header and claims bytes.
func verifySigned(token string, keys []byte) ([]byte, []byte, error) {
	if len(token) < 1 || len(token) > 16384 {
		return nil, nil, denied
	}
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return nil, nil, denied
	}
	decode := base64.RawURLEncoding.Strict().DecodeString
	header, err := decode(parts[0])
	if err != nil {
		return nil, nil, denied
	}
	claims, err := decode(parts[1])
	if err != nil {
		return nil, nil, denied
	}
	sig, err := decode(parts[2])
	if err != nil {
		return nil, nil, denied
	}
	var h struct {
		Alg  string
		Kid  string
		Crit json.RawMessage
		JKU  json.RawMessage
		X5U  json.RawMessage
		B64  json.RawMessage
	}
	if strictJSON(header, &h) != nil || h.Alg != "RS256" || len(h.Kid) == 0 || len(h.Kid) > 256 || len(h.Crit) > 0 || len(h.JKU) > 0 || len(h.X5U) > 0 || len(h.B64) > 0 {
		return nil, nil, denied
	}
	var set struct {
		Keys []struct{ Kty, Use, Alg, Kid, N, E string }
	}
	if strictJSON(keys, &set) != nil || len(set.Keys) < 1 || len(set.Keys) > 16 {
		return nil, nil, denied
	}
	var key *rsa.PublicKey
	for _, j := range set.Keys {
		if j.Kid != h.Kid {
			continue
		}
		if key != nil || j.Kty != "RSA" || j.Use != "sig" || j.Alg != "RS256" {
			return nil, nil, denied
		}
		n, e := decode(j.N)
		if e != nil || len(n) < 256 || len(n) > 1024 {
			return nil, nil, denied
		}
		exponent, e := decode(j.E)
		if e != nil || len(exponent) < 1 || len(exponent) > 4 {
			return nil, nil, denied
		}
		ev := new(big.Int).SetBytes(exponent).Int64()
		if ev < 3 || ev > 2147483647 || ev%2 == 0 {
			return nil, nil, denied
		}
		key = &rsa.PublicKey{N: new(big.Int).SetBytes(n), E: int(ev)}
	}
	if key == nil {
		return nil, nil, denied
	}
	hash := sha256.Sum256([]byte(parts[0] + "." + parts[1]))
	if rsa.VerifyPKCS1v15(key, crypto.SHA256, hash[:], sig) != nil {
		return nil, nil, denied
	}
	return header, claims, nil
}

func validateToken(token string, keys []byte, identity string, now, start, expires int64) error {
	_, claims, err := verifySigned(token, keys)
	if err != nil {
		return denied
	}
	// These checks follow signature verification. Decoding alone assures nothing.
	var c struct {
		Iss, Sub, Azp, Scope string
		Aud                  json.RawMessage
		Iat, Exp             int64
		Nbf                  *int64
		Operator             bool            `json:"jocasta_operator"`
		Identity             string          `json:"webmcp_identity"`
		Projects             json.RawMessage `json:"jocasta_projects"`
	}
	if strictJSON(claims, &c) != nil {
		return denied
	}
	var aud string
	if json.Unmarshal(c.Aud, &aud) != nil {
		var list []string
		if json.Unmarshal(c.Aud, &list) != nil || len(list) != 1 {
			return denied
		}
		aud = list[0]
	}
	if c.Iss != issuer || aud != resource || c.Azp != clientID || !exactScopes(c.Scope) || !c.Operator || c.Identity != identity || len(c.Projects) > 0 || len(c.Sub) < 1 || len(c.Sub) > 256 {
		return denied
	}
	if c.Iat <= 0 || c.Iat > now+5 || c.Exp-c.Iat <= 0 || c.Exp-c.Iat > 300 || c.Exp-now <= 30 || c.Exp-now > 300 || c.Iat < start-5 || c.Exp > start+expires+5 || (c.Nbf != nil && *c.Nbf > now) {
		return denied
	}
	return nil
}

// validateOV checks the signed OV contract after signature verification. It
// follows the OV verifier: one string audience, ov.read, a nonempty subject
// without control characters, at most 32 claims, an alg/kid/typ-only header,
// and the exact single admitted namespace, without any ov_actions claim. The
// OV scope mapping signs no account identity, so the subject is checked for
// shape, not compared.
func validateOV(token string, keys []byte, now, start, expires int64) error {
	return validateOVContract(token, keys, now, start, expires, ovNarrow)
}

// validateOVFull additionally requires the four OV scope families and exactly
// the resources root with all four signed actions; an old read-only grant shape
// is refused rather than treated as full access.
func validateOVFull(token string, keys []byte, now, start, expires int64) error {
	return validateOVContract(token, keys, now, start, expires, ovFull)
}

func validateOVContract(token string, keys []byte, now, start, expires int64, contract ovContract) error {
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
		if strings.HasPrefix(lower, "holonet_") || slices.Contains(ovForeign, lower) || (name != lower && slices.Contains(ovChecked, lower)) {
			return denied
		}
	}
	var iss, aud, azp, scope, sub string
	if !text(c["iss"], &iss) || iss != ovIssuer || !text(c["aud"], &aud) || aud != ovResource ||
		!text(c["azp"], &azp) || azp != ovClientID || !text(c["scope"], &scope) || !contract.scope(scope) ||
		!text(c["sub"], &sub) || !subject(sub) {
		return denied
	}
	var namespaces []string
	if raw, ok := c["ov_namespaces"]; !ok || json.Unmarshal(raw, &namespaces) != nil || len(namespaces) != 1 || namespaces[0] != contract.namespace {
		return denied
	}
	// Signed actions are an exact list: unknown, duplicate, missing or reordered
	// actions refuse, and the narrow mode admits no action claim at all.
	raw, present := c["ov_actions"]
	if contract.actions == nil {
		if present {
			return denied
		}
	} else {
		var actions []string
		if !present || len(raw) == 0 || raw[0] != '[' || json.Unmarshal(raw, &actions) != nil || !slices.Equal(actions, contract.actions) {
			return denied
		}
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

// text decodes a present JSON string; null, numbers, lists and objects fail.
func text(raw json.RawMessage, out *string) bool {
	return len(raw) > 0 && raw[0] == '"' && json.Unmarshal(raw, out) == nil
}

// integer decodes a present JSON integer; fractions, exponents and strings fail.
func integer(raw json.RawMessage, out *int64) bool {
	return len(raw) > 0 && (raw[0] == '-' || (raw[0] >= '0' && raw[0] <= '9')) && json.Unmarshal(raw, out) == nil
}

func subject(s string) bool {
	if !utf8.ValidString(s) {
		return false
	}
	count := 0
	for _, r := range s {
		if r < 32 {
			return false
		}
		count++
	}
	return count >= 1 && count <= 256
}
