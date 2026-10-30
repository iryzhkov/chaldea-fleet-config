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
	"net/http"
	"os"
	"os/user"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"
)

// The claims the multi-scope OV mapping signs for a full interactive account
// requesting all four families: the resources root and every action.
func ovFullFixture(t *testing.T) (*rsa.PrivateKey, []byte, map[string]any) {
	t.Helper()
	key, jwks, c := ovFixture(t)
	c["scope"] = ovFullScopes
	c["ov_namespaces"] = []string{"viking://resources"}
	c["ov_actions"] = []string{"read", "write", "remove", "maintain"}
	return key, jwks, c
}

func TestOVFullClosedModes(t *testing.T) {
	for _, host := range []string{"laptop", "omarchy-pc"} {
		if selectMode([]string{"ov-full", host}) != "ov-full" {
			t.Fatalf("full OV mode refused for %s", host)
		}
	}
	// The narrow mode is unchanged: laptop only, never omarchy-pc.
	if selectMode([]string{"ov", "laptop"}) != "ov" || selectMode([]string{"ov", "omarchy-pc"}) != "" {
		t.Fatal("narrow OV mode changed")
	}
	for _, args := range [][]string{{"ov-full"}, {"ov-full", "agent-a"}, {"ov-full", "agent-b"}, {"ov-full", "homelab"},
		{"ov-full", "controller"}, {"ov-full", "laptop", "extra"}, {"OV-FULL", "laptop"}, {"ov-full", "Laptop"},
		{"ov-full", "laptop "}, {"ov-full", ""}, {"ov_full", "laptop"}, {"ov-full", "--host=laptop"},
		{"ov-full", "laptop", "--scope=ov.read"}, {"laptop", "ov-full"}, {"jocasta", "ov-full"}} {
		if selectMode(args) != "" {
			t.Fatalf("open mode admitted: %q", args)
		}
	}
}

func TestOVFullHostBinding(t *testing.T) {
	if ovFullBinding("laptop", "omarchy-macbook-air-igor", 1001) != nil || ovFullBinding("omarchy-pc", "omarchy-pc", 1000) != nil {
		t.Fatal("bound host refused")
	}
	for _, tt := range []struct {
		host, node string
		uid        int
	}{
		{"laptop", "omarchy-pc", 1001}, {"laptop", "omarchy-macbook-air-igor", 1000}, {"omarchy-pc", "omarchy-pc", 1001},
		{"omarchy-pc", "omarchy-macbook-air-igor", 1000}, {"omarchy-pc", "OMARCHY-PC", 1000}, {"omarchy-pc", "omarchy-pc.lan", 1000},
		{"omarchy-pc", "omarchy-pc", 0}, {"agent-a", "agent-a", 1000}, {"", "", 0},
	} {
		if ovFullBinding(tt.host, tt.node, tt.uid) == nil {
			t.Fatalf("wrong machine or account admitted: %v", tt)
		}
	}
}

func TestOVFullSignedContract(t *testing.T) {
	key, jwks, valid := ovFullFixture(t)
	check := func(c map[string]any) error {
		return validateOVFull(signed(t, key, c), jwks, 2000000000, 2000000000, 300)
	}
	if check(valid) != nil {
		t.Fatal("valid full OV fixture refused")
	}
	permuted := copyClaims(valid)
	permuted["scope"] = "ov.maintain ov.remove ov.write ov.read"
	if check(permuted) != nil {
		t.Fatal("permuted exact scope set refused")
	}
	cases := []struct {
		name, field string
		value       any
	}{
		// Escalating or partial requests and old read-only grants are not full access.
		{"read-scope-only", "scope", "ov.read"}, {"missing-maintain", "scope", "ov.read ov.write ov.remove"},
		{"extra-scope", "scope", ovFullScopes + " offline_access"}, {"duplicate-scope", "scope", "ov.read ov.write ov.remove ov.remove"},
		{"double-space", "scope", "ov.read  ov.write ov.remove ov.maintain"}, {"tab", "scope", "ov.read\tov.write ov.remove ov.maintain"},
		{"list-scope", "scope", strings.Split(ovFullScopes, " ")}, {"foreign-scope", "scope", "ov.read ov.write ov.remove ha.control"},
		{"read-action-only", "ov_actions", []string{"read"}}, {"partial-actions", "ov_actions", []string{"read", "write"}},
		{"reordered-actions", "ov_actions", []string{"write", "read", "remove", "maintain"}},
		{"duplicate-action", "ov_actions", []string{"read", "write", "remove", "maintain", "maintain"}},
		{"unknown-action", "ov_actions", []string{"read", "write", "remove", "maintain", "admin"}},
		{"wildcard-action", "ov_actions", []string{"*"}}, {"string-actions", "ov_actions", "read write remove maintain"},
		{"null-actions", "ov_actions", nil}, {"empty-actions", "ov_actions", []string{}},
		{"object-actions", "ov_actions", map[string]bool{"read": true}}, {"numeric-actions", "ov_actions", []int{1, 2, 3, 4}},
		{"narrow-namespace", "ov_namespaces", []string{ovNamespace}}, {"slash-root", "ov_namespaces", []string{"viking://resources/"}},
		{"root-and-child", "ov_namespaces", []string{"viking://resources", "viking://resources/a"}},
		{"user-store", "ov_namespaces", []string{"viking://user"}}, {"agent-store", "ov_namespaces", []string{"viking://agent"}},
		{"whole-store", "ov_namespaces", []string{"viking://"}}, {"string-namespace", "ov_namespaces", "viking://resources"},
		{"issuer", "iss", issuer}, {"audience", "aud", resource}, {"client", "azp", clientID},
		{"folded-actions", "OV_ACTIONS", []string{"read"}}, {"jocasta-operator", "jocasta_operator", true},
		{"ha-actions", "ha_actions", []string{"state.read"}}, {"expired", "exp", 1999999999},
	}
	for _, tt := range cases {
		t.Run(tt.name, func(t *testing.T) {
			c := copyClaims(valid)
			c[tt.field] = tt.value
			if check(c) == nil {
				t.Fatal("invalid full OV fixture admitted")
			}
		})
	}
	for _, field := range []string{"ov_actions", "ov_namespaces", "scope"} {
		c := copyClaims(valid)
		delete(c, field)
		if check(c) == nil {
			t.Fatalf("missing %s admitted", field)
		}
	}
	// Duplicate claim names and a tampered grant never reach the action check.
	token := signed(t, key, valid)
	parts := strings.Split(token, ".")
	dup := strings.TrimSuffix(string(mustJSON(t, valid)), "}") + `,"ov_actions":["read"]}`
	parts[1] = encodedRaw(dup)
	if validateOVFull(strings.Join(parts, "."), jwks, 2000000000, 2000000000, 300) == nil {
		t.Fatal("unsigned duplicate claim admitted")
	}
	if validateOVFull(signedRaw(t, key, dup), jwks, 2000000000, 2000000000, 300) == nil {
		t.Fatal("signed duplicate claim admitted")
	}
	other, _, _ := fixture(t)
	if validateOVFull(token, jwksFor(other, "fixture"), 2000000000, 2000000000, 300) == nil {
		t.Fatal("other signer admitted")
	}
}

// The narrow mode keeps its exact old contract and never accepts an action claim.
func TestOVModesDoNotCross(t *testing.T) {
	key, jwks, full := ovFullFixture(t)
	_, _, narrow := ovFixture(t)
	_, _, jocastaClaims := fixture(t)
	if validateOV(signed(t, key, narrow), jwks, 2000000000, 2000000000, 300) != nil {
		t.Fatal("narrow OV fixture refused")
	}
	for name, c := range map[string]map[string]any{"full": full, "jocasta": jocastaClaims} {
		if validateOV(signed(t, key, c), jwks, 2000000000, 2000000000, 300) == nil {
			t.Fatalf("%s token admitted by narrow OV mode", name)
		}
	}
	for name, c := range map[string]map[string]any{"narrow": narrow, "jocasta": jocastaClaims} {
		if validateOVFull(signed(t, key, c), jwks, 2000000000, 2000000000, 300) == nil {
			t.Fatalf("%s token admitted by full OV mode", name)
		}
	}
	if validateToken(signed(t, key, full), jwks, "webmcp-interactive-laptop", 2000000000, 2000000000, 300) == nil {
		t.Fatal("full OV token admitted by Jocasta mode")
	}
	for _, actions := range [][]string{{"read"}, {"read", "write", "remove", "maintain"}} {
		c := copyClaims(narrow)
		c["ov_actions"] = actions
		if validateOV(signed(t, key, c), jwks, 2000000000, 2000000000, 300) == nil {
			t.Fatalf("narrow OV mode admitted signed actions %v", actions)
		}
	}
	folded := copyClaims(narrow)
	folded["Ov_Actions"] = []string{"read"}
	if validateOV(signed(t, key, folded), jwks, 2000000000, 2000000000, 300) == nil {
		t.Fatal("narrow OV mode admitted a folded action claim")
	}
}

func TestOVFullExchangeContract(t *testing.T) {
	key, jwks, c := ovFullFixture(t)
	token := signed(t, key, c)
	_, _, narrowClaims := ovFixture(t)
	narrow := signed(t, key, narrowClaims)
	const secret = "FixtureOVFullAppPassword0123456789"
	for _, host := range []string{"laptop", "omarchy-pc"} {
		for _, variant := range []string{"valid", "permuted", "read-scope", "partial-scope", "refresh", "narrow-token", "status", "long"} {
			t.Run(host+"/"+variant, func(t *testing.T) {
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
						if f.Get("password") != secret || f.Get("username") != "chaldea-"+host+"-ov-full-interactive" ||
							f.Get("scope") != ovFullRequestScopes || f.Get("client_id") != ovClientID ||
							f.Get("grant_type") != "client_credentials" || f.Has("resource") || len(f) != 5 {
							t.Fatal("exchange drift")
						}
						result := map[string]any{"access_token": token, "token_type": "Bearer", "expires_in": 300, "scope": ovFullScopes}
						switch variant {
						case "permuted":
							result["scope"] = "ov.write ov.read ov.maintain ov.remove"
						case "read-scope":
							result["scope"] = ovScope
						case "partial-scope":
							result["scope"] = "ov.read ov.write"
						case "refresh":
							result["refresh_token"] = "secret"
						case "narrow-token":
							result["access_token"] = narrow
						case "long":
							result["expires_in"] = 301
						}
						b, _ := json.Marshal(result)
						body = string(b)
						if variant == "status" {
							status, body = 400, secret
						}
					} else if req.URL.String() != ovJWKSURL || req.Method != "GET" || req.Header.Get("Authorization") != "" {
						t.Fatal("unapproved endpoint")
					}
					return &http.Response{StatusCode: status, Body: io.NopCloser(strings.NewReader(body)), Header: http.Header{}}, nil
				})
				got, e := acquireOVFull(context.Background(), client, host, secret, func() time.Time { return time.Unix(2000000000, 0) })
				if variant == "valid" || variant == "permuted" {
					if e != nil || got != token || calls != 2 {
						t.Fatal("exchange failed")
					}
				} else if e == nil || e.Error() != denied.Error() || got != "" {
					t.Fatal("failure leaked or admitted")
				}
			})
		}
	}
	// An unselected host never reaches the network.
	client := httpClient()
	client.Transport = roundTrip(func(*http.Request) (*http.Response, error) {
		t.Fatal("unselected host made a request")
		return nil, nil
	})
	for _, host := range []string{"agent-a", "controller", ""} {
		if _, e := acquireOVFull(context.Background(), client, host, secret, time.Now); e == nil {
			t.Fatalf("unselected host %q admitted", host)
		}
	}
}

// The full credential path comes from the account database and is its own file.
func TestOVFullCredentialPath(t *testing.T) {
	account, err := user.LookupId(strconv.Itoa(os.Getuid()))
	if err != nil {
		t.Fatal("this UID has no account database entry")
	}
	t.Setenv("HOME", t.TempDir())
	path, err := credentialPath(os.Getuid(), ovFullCredential)
	if err != nil || path != filepath.Join(account.HomeDir, ".config/chaldea/authentik/ov-full-interactive.app-password") {
		t.Fatal("full credential path followed the environment or drifted")
	}
	narrow, err := ovCredentialPath(os.Getuid())
	if err != nil || narrow == path || !strings.HasSuffix(narrow, "/ov-interactive-codex.app-password") {
		t.Fatal("narrow credential path changed")
	}
}

func mustJSON(t *testing.T, v any) []byte {
	t.Helper()
	b, e := json.Marshal(v)
	if e != nil {
		t.Fatal(e)
	}
	return b
}

func encodedRaw(s string) string { return base64.RawURLEncoding.EncodeToString([]byte(s)) }

// signedRaw signs claims text verbatim, so a duplicate name survives encoding.
func signedRaw(t *testing.T, key *rsa.PrivateKey, claims string) string {
	t.Helper()
	data := encoded(map[string]any{"alg": "RS256", "kid": "fixture"}) + "." + encodedRaw(claims)
	h := sha256.Sum256([]byte(data))
	sig, e := rsa.SignPKCS1v15(rand.Reader, key, crypto.SHA256, h[:])
	if e != nil {
		t.Fatal(e)
	}
	return data + "." + base64.RawURLEncoding.EncodeToString(sig)
}
