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
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func encoded(v any) string { b, _ := json.Marshal(v); return base64.RawURLEncoding.EncodeToString(b) }
func signed(t *testing.T, key *rsa.PrivateKey, c map[string]any) string {
	t.Helper()
	data := encoded(map[string]any{"alg": "RS256", "kid": "fixture"}) + "." + encoded(c)
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
