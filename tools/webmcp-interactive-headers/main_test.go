package main

import (
	"context"
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"io"
	"math/big"
	"net/http"
	"net/http/httptest"
	"os"
	"os/user"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"
)

func encoded(v any) string { b, _ := json.Marshal(v); return base64.RawURLEncoding.EncodeToString(b) }
func signed(t *testing.T, key *rsa.PrivateKey, c map[string]any) string {
	t.Helper()
	return signedWith(t, key, map[string]any{"alg": "RS256", "kid": "fixture"}, c)
}
func signedWith(t *testing.T, key *rsa.PrivateKey, header, c map[string]any) string {
	t.Helper()
	data := encoded(header) + "." + encoded(c)
	h := sha256.Sum256([]byte(data))
	sig, e := rsa.SignPKCS1v15(rand.Reader, key, crypto.SHA256, h[:])
	if e != nil {
		t.Fatal(e)
	}
	return data + "." + base64.RawURLEncoding.EncodeToString(sig)
}
func fixture(t *testing.T) (*rsa.PrivateKey, []byte, map[string]any) {
	t.Helper()
	key, e := rsa.GenerateKey(rand.Reader, 2048)
	if e != nil {
		t.Fatal(e)
	}
	jwks, _ := json.Marshal(map[string]any{"keys": []any{map[string]any{"kty": "RSA", "use": "sig", "alg": "RS256", "kid": "fixture",
		"n": base64.RawURLEncoding.EncodeToString(key.N.Bytes()), "e": base64.RawURLEncoding.EncodeToString(big.NewInt(int64(key.E)).Bytes())}}})
	return key, jwks, map[string]any{"iss": issuer, "sub": "fixture-subject", "aud": resource, "azp": clientID, "scope": scopes,
		"jocasta_operator": true, "webmcp_identity": "webmcp-interactive-laptop", "iat": int64(2000000000), "exp": int64(2000000300)}
}
func TestSignedContract(t *testing.T) {
	key, jwks, valid := fixture(t)
	check := func(c map[string]any) error {
		return validateToken(signed(t, key, c), jwks, "webmcp-interactive-laptop", 2000000000, 2000000000, 300)
	}
	if check(valid) != nil {
		t.Fatal("valid signed fixture refused")
	}
	cases := []struct {
		name, field string
		value       any
	}{
		{"issuer", "iss", issuer + "other"}, {"resource", "aud", "https://other.invalid/mcp"}, {"client", "azp", "other"},
		{"identity", "webmcp_identity", "webmcp-interactive-agent-a"}, {"operator", "jocasta_operator", false},
		{"missing-scope", "scope", "jocasta.read"}, {"extra-scope", "scope", scopes + " offline_access"},
		{"duplicate-scope", "scope", "jocasta.read jocasta.read"}, {"project", "jocasta_projects", []string{}},
		{"expired", "exp", 1999999999}, {"reserve", "exp", 2000000030}, {"long", "exp", 2000000301},
		{"future-iat", "iat", 2000000006}, {"old-token", "iat", 1999999990}, {"nbf", "nbf", 2000000001},
		{"empty-sub", "sub", ""}, {"duplicate-aud", "aud", []string{resource, resource}},
	}
	for _, tt := range cases {
		t.Run(tt.name, func(t *testing.T) {
			c := map[string]any{}
			for k, v := range valid {
				c[k] = v
			}
			c[tt.field] = tt.value
			if check(c) == nil {
				t.Fatal("invalid signed fixture admitted")
			}
		})
	}
	token := signed(t, key, valid)
	parts := strings.Split(token, ".")
	parts[1] = encoded(map[string]any{"iss": issuer})
	if validateToken(strings.Join(parts, "."), jwks, "webmcp-interactive-laptop", 2000000000, 2000000000, 300) == nil {
		t.Fatal("tamper admitted")
	}
	if validateToken(token, []byte(`{"keys":[]}`), "webmcp-interactive-laptop", 2000000000, 2000000000, 300) == nil {
		t.Fatal("unknown signer admitted")
	}
	if validateToken(token, jwks, "webmcp-interactive-agent-a", 2000000000, 2000000000, 300) == nil {
		t.Fatal("wrong host admitted")
	}
}

type roundTrip func(*http.Request) (*http.Response, error)

func (f roundTrip) RoundTrip(r *http.Request) (*http.Response, error) { return f(r) }
func TestExchangeContract(t *testing.T) {
	key, jwks, c := fixture(t)
	token := signed(t, key, c)
	for _, variant := range []string{"valid", "refresh", "scope", "status", "malformed", "oversized", "duplicate"} {
		t.Run(variant, func(t *testing.T) {
			calls := 0
			client := httpClient()
			client.Transport = roundTrip(func(req *http.Request) (*http.Response, error) {
				calls++
				body := string(jwks)
				status := 200
				if req.URL.String() == tokenURL {
					if req.Method != "POST" || req.ParseForm() != nil {
						t.Fatal("bad request")
					}
					if req.PostForm.Get("password") != "fixture-secret-password" || req.PostForm.Get("username") != "webmcp-interactive-laptop" || req.PostForm.Get("scope") != scopes || req.PostForm.Get("resource") != resource || req.PostForm.Get("client_id") != clientID || req.PostForm.Get("grant_type") != "client_credentials" || len(req.PostForm) != 6 {
						t.Fatal("exchange drift")
					}
					result := map[string]any{"access_token": token, "token_type": "Bearer", "expires_in": 300, "scope": scopes}
					if variant == "refresh" {
						result["refresh_token"] = "secret"
					}
					if variant == "scope" {
						result["scope"] = "jocasta.read"
					}
					b, _ := json.Marshal(result)
					body = string(b)
					switch variant {
					case "status":
						status = 400
						body = "fixture-secret-password"
					case "malformed":
						body = "fixture-secret-password"
					case "oversized":
						body = strings.Repeat("x", 32769)
					case "duplicate":
						body = `{"access_token":"one","access_token":"two"}`
					}
				} else if req.URL.String() != jwksURL || req.Method != "GET" || req.Header.Get("Authorization") != "" {
					t.Fatal("unapproved endpoint")
				}
				return &http.Response{StatusCode: status, Body: io.NopCloser(strings.NewReader(body)), Header: http.Header{}}, nil
			})
			got, e := acquire(context.Background(), client, enrollment{Username: "webmcp-interactive-laptop", Password: "fixture-secret-password"}, func() time.Time { return time.Unix(2000000000, 0) })
			if variant == "valid" {
				if e != nil || got != token || calls != 2 {
					t.Fatal("exchange failed")
				}
			} else if e == nil || e.Error() != denied.Error() || got != "" {
				t.Fatal("failure leaked or admitted")
			}
		})
	}
}
func TestRedirectAndBounds(t *testing.T) {
	count := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { count++; http.Redirect(w, r, "/secret", 302) }))
	defer server.Close()
	_, e := response(context.Background(), httpClient(), "GET", server.URL, nil, 10)
	if e == nil || e.Error() != denied.Error() || count != 1 {
		t.Fatal("redirect followed or leaked")
	}
	client := httpClient()
	tr := client.Transport.(*http.Transport)
	if tr.Proxy != nil || tr.TLSClientConfig != nil || client.Timeout > 8*time.Second {
		t.Fatal("network trust weakened")
	}
	for _, data := range []string{`{"a":1,"a":2}`, `{"a":{"b":1,"b":2}}`, `{} {}`} {
		var out any
		if strictJSON([]byte(data), &out) == nil {
			t.Fatal("ambiguous JSON admitted")
		}
	}
}
func TestProtectedEnrollment(t *testing.T) {
	dir := t.TempDir()
	os.Chmod(dir, 0700)
	path := filepath.Join(dir, "enrollment.json")
	value := enrollment{Version: 1, Host: "laptop", Username: "webmcp-interactive-laptop", Password: "fixture-secret-password", Generation: 1, Owner: "00000000-0000-4000-8000-000000000000"}
	data, _ := json.Marshal(value)
	reset := func() {
		os.Remove(path)
		if e := os.WriteFile(path, data, 0600); e != nil {
			t.Fatal(e)
		}
	}
	reset()
	if _, e := readEnrollment(path, os.Getuid(), "laptop"); e != nil {
		t.Fatal("safe credential refused")
	}
	if _, e := readEnrollment(path, os.Getuid(), "agent-a"); e == nil {
		t.Fatal("wrong host")
	}
	if _, e := readEnrollment(path, os.Getuid()+1, "laptop"); e == nil {
		t.Fatal("wrong UID")
	}
	os.Chmod(path, 0640)
	if _, e := readEnrollment(path, os.Getuid(), "laptop"); e == nil {
		t.Fatal("shared credential")
	}
	reset()
	other := filepath.Join(dir, "link")
	os.Link(path, other)
	if _, e := readEnrollment(path, os.Getuid(), "laptop"); e == nil {
		t.Fatal("hard link")
	}
	os.Remove(other)
	reset()
	os.Remove(path)
	os.Symlink("missing", path)
	if _, e := readEnrollment(path, os.Getuid(), "laptop"); e == nil {
		t.Fatal("symlink")
	}
	reset()
	os.Chmod(dir, 0770)
	if _, e := readEnrollment(path, os.Getuid(), "laptop"); e == nil {
		t.Fatal("shared directory")
	}
	os.Chmod(dir, 0700)
	reset()
	os.WriteFile(path, []byte(strings.Repeat("x", 4097)), 0600)
	if _, e := readEnrollment(path, os.Getuid(), "laptop"); e == nil {
		t.Fatal("oversized credential")
	}
}

func TestClosedModes(t *testing.T) {
	for _, host := range []string{"laptop", "agent-a", "agent-b", "omarchy-pc"} {
		if selectMode([]string{"jocasta", host}) != "jocasta" {
			t.Fatal("Jocasta host mode refused")
		}
	}
	if selectMode([]string{"ov", "laptop"}) != "ov" {
		t.Fatal("OV laptop mode refused")
	}
	for _, args := range [][]string{{}, {"ov"}, {"ov", "agent-a"}, {"ov", "agent-b"}, {"ov", "omarchy-pc"},
		{"ov", "laptop", "extra"}, {"OV", "laptop"}, {"ov", "Laptop"}, {"ov", "laptop "}, {"ov-laptop"},
		{"ov", "--url=https://other.invalid/mcp"}, {"ov", "laptop", "--scope=ov.write"}, {"jocasta"},
		{"jocasta", "homelab"}, {"jocasta", "laptop", "ov"}, {"ha", "laptop"}, {"homelab", "laptop"}, {"laptop", "ov"}} {
		if selectMode(args) != "" {
			t.Fatalf("open mode admitted: %q", args)
		}
	}
}

func jwksFor(key *rsa.PrivateKey, kid string) []byte {
	data, _ := json.Marshal(map[string]any{"keys": []any{map[string]any{"kty": "RSA", "use": "sig", "alg": "RS256", "kid": kid,
		"n": base64.RawURLEncoding.EncodeToString(key.N.Bytes()), "e": base64.RawURLEncoding.EncodeToString(big.NewInt(int64(key.E)).Bytes())}}})
	return data
}

// The claims Authentik signs for the OV provider: its fixed audience and grant
// from the scope mapping, plus default claims the verifier ignores.
func ovFixture(t *testing.T) (*rsa.PrivateKey, []byte, map[string]any) {
	t.Helper()
	key, jwks, _ := fixture(t)
	return key, jwks, map[string]any{"iss": ovIssuer, "sub": "fixture-hashed-subject", "aud": ovResource, "azp": ovClientID,
		"scope": ovScope, "ov_namespaces": []string{ovNamespace}, "iat": int64(2000000000), "exp": int64(2000000300),
		"auth_time": int64(2000000000), "acr": "goauthentik.io/providers/oauth2/default", "amr": []string{"pwd"}, "uid": "fixture-uid"}
}

func copyClaims(c map[string]any) map[string]any {
	out := map[string]any{}
	for k, v := range c {
		out[k] = v
	}
	return out
}

func TestOVSignedContract(t *testing.T) {
	key, jwks, valid := ovFixture(t)
	base := map[string]any{"alg": "RS256", "kid": "fixture"}
	check := func(header, c map[string]any) error {
		return validateOV(signedWith(t, key, header, c), jwks, 2000000000, 2000000000, 300)
	}
	for _, header := range []map[string]any{base, {"alg": "RS256", "kid": "fixture", "typ": "JWT"}, {"alg": "RS256", "kid": "fixture", "typ": "at+jwt"}} {
		if check(header, valid) != nil {
			t.Fatal("valid signed OV fixture refused")
		}
	}
	long := map[string]any{}
	for i := 0; i < 21; i++ {
		long["extra_"+strconv.Itoa(i)] = i
	}
	cases := []struct {
		name, field string
		value       any
	}{
		{"issuer", "iss", ovIssuer + "other"}, {"jocasta-issuer", "iss", issuer},
		{"audience", "aud", "https://other.invalid/mcp"}, {"jocasta-audience", "aud", resource},
		{"audience-list", "aud", []string{ovResource}}, {"client", "azp", "other"}, {"jocasta-client", "azp", clientID},
		{"empty-scope", "scope", ""}, {"jocasta-scope", "scope", "jocasta.read"}, {"extra-scope", "scope", "ov.read offline_access"},
		{"duplicate-scope", "scope", "ov.read ov.read"}, {"list-scope", "scope", []string{ovScope}},
		{"wider-namespace", "ov_namespaces", []string{"viking://resources"}},
		{"parent-namespace", "ov_namespaces", []string{"viking://resources/homeassistant-api"}},
		{"sibling-namespace", "ov_namespaces", []string{"viking://resources/homeassistant-api/ov-canary-denied-a63e197f"}},
		{"child-namespace", "ov_namespaces", []string{ovNamespace + "/child"}},
		{"extra-namespace", "ov_namespaces", []string{ovNamespace, "viking://resources/other"}},
		{"duplicate-namespace", "ov_namespaces", []string{ovNamespace, ovNamespace}},
		{"empty-namespaces", "ov_namespaces", []string{}}, {"string-namespace", "ov_namespaces", ovNamespace},
		{"null-namespaces", "ov_namespaces", nil},
		{"expired", "exp", 1999999999}, {"reserve", "exp", 2000000030}, {"long", "exp", 2000000301},
		{"future-iat", "iat", 2000000006}, {"old-token", "iat", 1999999990}, {"nbf", "nbf", 2000000001},
		{"string-nbf", "nbf", "2000000000"}, {"fraction-iat", "iat", 2000000000.5}, {"string-exp", "exp", "2000000300"},
		{"empty-sub", "sub", ""}, {"control-sub", "sub", "fixture\nsubject"}, {"long-sub", "sub", strings.Repeat("s", 257)},
		{"number-sub", "sub", 7},
		{"jocasta-operator", "jocasta_operator", true}, {"jocasta-identity", "webmcp_identity", "webmcp-interactive-laptop"},
		{"jocasta-projects", "jocasta_projects", []string{"tooling"}}, {"homelab-grant", "homelab_hosts", []string{}},
		{"ha-grant", "ha_actions", []string{"state.read"}}, {"holonet-grant", "holonet_actions", []string{}},
		{"generic-grants", "grants", []string{}}, {"folded-issuer", "ISS", ovIssuer},
		{"folded-grant", "Ov_namespaces", []string{"viking://resources"}}, {"folded-foreign", "Jocasta_Operator", true},
		{"oversized", "pad", strings.Repeat("x", 12288)},
	}
	for _, tt := range cases {
		t.Run(tt.name, func(t *testing.T) {
			c := copyClaims(valid)
			c[tt.field] = tt.value
			if check(base, c) == nil {
				t.Fatal("invalid signed OV fixture admitted")
			}
		})
	}
	if check(base, map[string]any{"iss": ovIssuer}) == nil {
		t.Fatal("incomplete claims admitted")
	}
	for _, field := range []string{"iss", "aud", "azp", "scope", "sub", "iat", "exp", "ov_namespaces"} {
		c := copyClaims(valid)
		delete(c, field)
		if check(base, c) == nil {
			t.Fatalf("missing %s admitted", field)
		}
	}
	many := copyClaims(valid)
	for k, v := range long {
		many[k] = v
	}
	if len(many) != 33 || check(base, many) == nil {
		t.Fatal("more than 32 claims admitted")
	}
	for _, header := range []map[string]any{
		{"alg": "RS256", "kid": "fixture", "typ": "other"}, {"alg": "RS256", "kid": "fixture", "typ": 1},
		{"alg": "RS256", "kid": "fixture", "x5t": "fixture"}, {"alg": "RS256", "kid": "fixture", "cty": "JWT"},
		{"alg": "RS256", "kid": "fixture", "jku": "https://other.invalid/jwks"}, {"alg": "HS256", "kid": "fixture"},
		{"kid": "fixture"}, {"alg": "RS256"},
	} {
		if check(header, valid) == nil {
			t.Fatalf("unsafe header admitted: %v", header)
		}
	}
	// A key ID outside the verifier's alphabet is refused even when the JWKS has it.
	spaced := map[string]any{"alg": "RS256", "kid": "fixture key"}
	if validateOV(signedWith(t, key, spaced, valid), jwksFor(key, "fixture key"), 2000000000, 2000000000, 300) == nil {
		t.Fatal("unsafe key ID admitted")
	}
	token := signed(t, key, valid)
	parts := strings.Split(token, ".")
	forged := copyClaims(valid)
	forged["ov_namespaces"] = []string{"viking://resources"}
	parts[1] = encoded(forged)
	if validateOV(strings.Join(parts, "."), jwks, 2000000000, 2000000000, 300) == nil {
		t.Fatal("tampered grant admitted")
	}
	if validateOV(token, []byte(`{"keys":[]}`), 2000000000, 2000000000, 300) == nil {
		t.Fatal("unknown signer admitted")
	}
	other, _, _ := fixture(t)
	if validateOV(token, jwksFor(other, "fixture"), 2000000000, 2000000000, 300) == nil {
		t.Fatal("other key with the same ID admitted")
	}
	if validateOV(token, jwks, 2000000000, 2000000000, 300) != nil {
		t.Fatal("valid token refused")
	}
}

// Neither mode accepts the other service's correctly signed token.
func TestCrossModeTokensRefused(t *testing.T) {
	key, jwks, jocastaClaims := fixture(t)
	_, _, ovClaims := ovFixture(t)
	jocastaToken, ovToken := signed(t, key, jocastaClaims), signed(t, key, ovClaims)
	if validateToken(jocastaToken, jwks, "webmcp-interactive-laptop", 2000000000, 2000000000, 300) != nil ||
		validateOV(ovToken, jwks, 2000000000, 2000000000, 300) != nil {
		t.Fatal("own-mode fixture refused")
	}
	if validateOV(jocastaToken, jwks, 2000000000, 2000000000, 300) == nil {
		t.Fatal("Jocasta token admitted by OV mode")
	}
	if validateToken(ovToken, jwks, "webmcp-interactive-laptop", 2000000000, 2000000000, 300) == nil {
		t.Fatal("OV token admitted by Jocasta mode")
	}
	mixed := copyClaims(ovClaims)
	mixed["jocasta_operator"], mixed["webmcp_identity"] = true, "webmcp-interactive-laptop"
	if validateOV(signed(t, key, mixed), jwks, 2000000000, 2000000000, 300) == nil {
		t.Fatal("OV token carrying Jocasta operator claims admitted")
	}
}

func TestOVExchangeContract(t *testing.T) {
	key, jwks, c := ovFixture(t)
	token := signed(t, key, c)
	_, _, jocastaClaims := fixture(t)
	foreign := signed(t, key, jocastaClaims)
	for _, variant := range []string{"valid", "refresh", "scope", "jocasta-scope", "short", "long", "status", "malformed", "oversized", "duplicate", "foreign-token"} {
		t.Run(variant, func(t *testing.T) {
			calls := 0
			client := httpClient()
			client.Transport = roundTrip(func(req *http.Request) (*http.Response, error) {
				calls++
				body := string(jwks)
				status := 200
				if req.URL.String() == tokenURL {
					if req.Method != "POST" || req.ParseForm() != nil {
						t.Fatal("bad request")
					}
					f := req.PostForm
					if f.Get("password") != "FixtureOVAppPassword0123456789" || f.Get("username") != ovUsername || f.Get("scope") != ovScope ||
						f.Get("client_id") != ovClientID || f.Get("grant_type") != "client_credentials" || f.Has("resource") || len(f) != 5 {
						t.Fatal("exchange drift")
					}
					result := map[string]any{"access_token": token, "token_type": "Bearer", "expires_in": 300, "scope": ovScope}
					switch variant {
					case "refresh":
						result["refresh_token"] = "secret"
					case "scope":
						result["scope"] = "ov.read offline_access"
					case "jocasta-scope":
						result["scope"] = scopes
					case "short":
						result["expires_in"] = 30
					case "long":
						result["expires_in"] = 301
					case "foreign-token":
						result["access_token"] = foreign
					}
					b, _ := json.Marshal(result)
					body = string(b)
					switch variant {
					case "status":
						status = 400
						body = "FixtureOVAppPassword0123456789"
					case "malformed":
						body = "FixtureOVAppPassword0123456789"
					case "oversized":
						body = strings.Repeat("x", 32769)
					case "duplicate":
						body = `{"access_token":"one","access_token":"two"}`
					}
				} else if req.URL.String() != ovJWKSURL || req.Method != "GET" || req.Header.Get("Authorization") != "" {
					t.Fatal("unapproved endpoint")
				}
				return &http.Response{StatusCode: status, Body: io.NopCloser(strings.NewReader(body)), Header: http.Header{}}, nil
			})
			got, e := acquireOV(context.Background(), client, "FixtureOVAppPassword0123456789", func() time.Time { return time.Unix(2000000000, 0) })
			if variant == "valid" {
				if e != nil || got != token || calls != 2 {
					t.Fatal("exchange failed")
				}
			} else if e == nil || e.Error() != denied.Error() || got != "" {
				t.Fatal("failure leaked or admitted")
			}
		})
	}
}

func TestOVCredentialCustody(t *testing.T) {
	dir := t.TempDir()
	os.Chmod(dir, 0700)
	private := filepath.Join(dir, "authentik")
	if e := os.Mkdir(private, 0700); e != nil {
		t.Fatal(e)
	}
	path := filepath.Join(private, "ov-interactive-codex.app-password")
	const secret = "FixtureOVAppPassword0123456789"
	reset := func(content string) {
		t.Helper()
		os.Remove(path)
		if e := os.WriteFile(path, []byte(content), 0600); e != nil {
			t.Fatal(e)
		}
	}
	refused := func(name, candidate string) {
		t.Helper()
		if got, e := readOVCredential(candidate, os.Getuid()); e == nil || got != "" || e.Error() != denied.Error() {
			t.Fatal(name + " admitted")
		}
	}
	reset(secret)
	if got, e := readOVCredential(path, os.Getuid()); e != nil || got != secret {
		t.Fatal("safe credential refused")
	}
	if _, e := readOVCredential(path, os.Getuid()+1); e == nil {
		t.Fatal("wrong UID admitted")
	}
	refused("relative path", "authentik/ov-interactive-codex.app-password")
	refused("unclean path", private+"/../authentik/ov-interactive-codex.app-password")
	for _, mode := range []os.FileMode{0640, 0604, 0644, 0400, 0700} {
		os.Chmod(path, mode)
		refused("mode "+mode.String(), path)
	}
	os.Chmod(path, 0600)
	for _, mode := range []os.FileMode{0750, 0770, 0701, 0755} {
		os.Chmod(private, mode)
		refused("directory mode "+mode.String(), path)
	}
	os.Chmod(private, 0700)
	os.Chmod(dir, 0777)
	refused("shared-writable ancestor", path)
	os.Chmod(dir, 0700)
	link := filepath.Join(private, "link")
	os.Link(path, link)
	refused("hard link", path)
	os.Remove(link)
	elsewhere := filepath.Join(dir, "elsewhere")
	os.Mkdir(elsewhere, 0700)
	os.WriteFile(filepath.Join(elsewhere, "target"), []byte(secret), 0600)
	os.Remove(path)
	os.Symlink(filepath.Join(elsewhere, "target"), path)
	refused("symlinked credential", path)
	os.Remove(path)
	alias := filepath.Join(dir, "alias")
	os.Symlink(elsewhere, alias)
	refused("symlinked ancestor", filepath.Join(alias, "target"))
	os.Mkdir(path, 0700)
	refused("directory credential", path)
	os.Remove(path)
	for name, content := range map[string]string{"newline": secret + "\n", "space": "Fixture OV App Password 0123",
		"short": "short-secret", "long": strings.Repeat("x", 257), "empty": "", "non-ascii": secret + "é",
		"control": secret + "\x7f"} {
		reset(content)
		refused(name, path)
	}
	reset(strings.Repeat("x", 256))
	if got, e := readOVCredential(path, os.Getuid()); e != nil || got != strings.Repeat("x", 256) {
		t.Fatal("maximum credential refused")
	}
	refused("missing", filepath.Join(private, "ov-tooling-codex.app-password"))
}

// The credential is found from the account database, never from HOME.
func TestOVCredentialPathIgnoresEnvironment(t *testing.T) {
	account, err := user.LookupId(strconv.Itoa(os.Getuid()))
	if err != nil {
		t.Skip("this UID has no account database entry")
	}
	fake := t.TempDir()
	t.Setenv("HOME", fake)
	t.Setenv("USER", "someone-else")
	path, err := ovCredentialPath(os.Getuid())
	if err != nil || path != filepath.Join(account.HomeDir, ovCredential) || strings.HasPrefix(path, fake) {
		t.Fatal("credential path followed the environment")
	}
	if !strings.HasSuffix(path, "/.config/chaldea/authentik/ov-interactive-codex.app-password") || strings.Contains(path, "ov-tooling-codex") {
		t.Fatal("credential path is not the interactive OV file")
	}
}
