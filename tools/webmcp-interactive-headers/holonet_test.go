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
	"strings"
	"testing"
	"time"
)

func holonetFixture(t *testing.T) (*rsa.PrivateKey, []byte, map[string]any) {
	key, keys, _ := fixture(t)
	return key, keys, map[string]any{"iss": holonetIssuer, "sub": "ordinary-reader-subject", "aud": holonetResource, "azp": holonetClientID, "scope": holonetScope,
		"iat": int64(2000000000), "exp": int64(2000000300), "holonet_server": holonetServer, "holonet_libraries": []string{"3"},
		"holonet_catalog_users": []string{holonetUser}, "holonet_history_users": []string{}, "holonet_target_users": []string{},
		"holonet_actions": []string{"catalog.read"}, "holonet_namespace": "movies-catalog"}
}
func TestHolonetClosedTupleAndActualHostBinding(t *testing.T) {
	if selectMode([]string{"holonet", "laptop"}) != "holonet" || holonetBinding("omarchy-macbook-air-igor", 1001) != nil {
		t.Fatal("closed tuple refused")
	}
	for _, args := range [][]string{{"holonet"}, {"holonet", "agent-a"}, {"holonet", "omarchy-pc"}, {"holonet", "laptop", "--path"}, {holonetResource, "laptop"}} {
		if selectMode(args) != "" {
			t.Fatal("unapproved tuple", args)
		}
	}
	for _, binding := range []struct {
		node string
		uid  int
	}{{"other", 1001}, {"omarchy-macbook-air-igor", 0}, {"omarchy-macbook-air-igor", 1000}} {
		if holonetBinding(binding.node, binding.uid) == nil {
			t.Fatal("foreign host binding")
		}
	}
	if strings.Contains(holonetCredential, "movies-catalog-claude") || !strings.HasSuffix(holonetCredential, "/holonet-interactive.app-password") {
		t.Fatal("limited/ordinary custody crossed")
	}
}

func TestHolonetSignedCatalogOnlyContract(t *testing.T) {
	key, keys, valid := holonetFixture(t)
	check := func(c map[string]any) error {
		return validateHolonet(signed(t, key, c), keys, 2000000000, 2000000000, 300)
	}
	if check(valid) != nil {
		t.Fatal("valid contract refused")
	}
	for _, tc := range []struct {
		name, field string
		value       any
	}{
		{"issuer", "iss", ovIssuer}, {"audience", "aud", resource}, {"audience array", "aud", []string{holonetResource}},
		{"client", "azp", clientID}, {"scope", "scope", "holonet.read holonet.curate"}, {"scope alias", "Scope", holonetScope},
		{"unicode alias", "ſcope", holonetScope}, {"server", "holonet_server", strings.Repeat("f", 32)},
		{"library", "holonet_libraries", []string{"4"}}, {"two libraries", "holonet_libraries", []string{"3", "4"}},
		{"numeric library", "holonet_libraries", []int{3}}, {"catalog user", "holonet_catalog_users", []string{strings.Repeat("f", 32)}},
		{"history", "holonet_history_users", []string{holonetUser}}, {"null history", "holonet_history_users", nil},
		{"target", "holonet_target_users", []string{holonetUser}}, {"action", "holonet_actions", []string{"userdata.read"}},
		{"unknown holonet", "holonet_admin", true}, {"namespace", "holonet_namespace", "other"},
		{"operator", "jocasta_operator", true}, {"foreign ov", "ov_namespaces", []string{"viking://"}},
		{"legacy grant", "grants", []any{}}, {"expired", "exp", 1999999999}, {"long", "exp", 2000000301},
		{"too little reserve", "exp", 2000000030}, {"old issue", "iat", 1999999990}, {"future issue", "iat", 2000000006},
		{"fraction issue", "iat", json.Number("2000000000.0")}, {"exponent expiry", "exp", json.Number("2.0000003e9")},
		{"future notbefore", "nbf", 2000000001}, {"null notbefore", "nbf", nil},
		{"control subject", "sub", "bad\u007fsubject"}, {"long utf8 subject", "sub", strings.Repeat("é", 200)},
	} {
		t.Run(tc.name, func(t *testing.T) {
			c := map[string]any{}
			for k, v := range valid {
				c[k] = v
			}
			c[tc.field] = tc.value
			if e := check(c); e == nil || e.Error() != denied.Error() {
				t.Fatal("invalid signed contract admitted or unsafe error")
			}
		})
	}
	for _, field := range []string{"holonet_history_users", "holonet_target_users", "holonet_actions", "holonet_namespace", "holonet_server"} {
		c := map[string]any{}
		for k, v := range valid {
			c[k] = v
		}
		delete(c, field)
		if check(c) == nil {
			t.Fatal("missing grant", field)
		}
	}
	for _, h := range []map[string]any{{"alg": "RS256", "kid": "fixture", "jku": "https://untrusted.invalid"}, {"alg": "RS256", "kid": "fixture", "typ": "other"}, {"alg": "RS256", "kid": "fixture", "ALG": "RS256"}} {
		if validateHolonet(signedWith(t, key, h, valid), keys, 2000000000, 2000000000, 300) == nil {
			t.Fatal("header escape admitted")
		}
	}
	// Signed duplicate names must fail, not silently replace an authority field.
	claims, _ := json.Marshal(valid)
	dup := strings.Replace(string(claims), `"holonet_libraries":["3"]`, `"holonet_libraries":["3"],"holonet_libraries":["4"]`, 1)
	if dup == string(claims) {
		t.Fatal("duplicate fixture not constructed")
	}
	data := encoded(map[string]any{"alg": "RS256", "kid": "fixture"}) + "." + base64.RawURLEncoding.EncodeToString([]byte(dup))
	digest := sha256.Sum256([]byte(data))
	sig, e := rsa.SignPKCS1v15(rand.Reader, key, crypto.SHA256, digest[:])
	if e != nil {
		t.Fatal(e)
	}
	if validateHolonet(data+"."+base64.RawURLEncoding.EncodeToString(sig), keys, 2000000000, 2000000000, 300) == nil {
		t.Fatal("duplicate signed authority admitted")
	}
	if validateHolonet(signed(t, key, valid), []byte(`{"keys":[]}`), 2000000000, 2000000000, 300) == nil {
		t.Fatal("unknown signer admitted")
	}
}

func TestHolonetPrivateExchangeEndpointsAndFailureProjection(t *testing.T) {
	key, keys, claims := holonetFixture(t)
	token := signed(t, key, claims)
	for _, variant := range []string{"valid", "scope", "refresh", "status", "oversized", "wrong-jwks"} {
		t.Run(variant, func(t *testing.T) {
			calls := 0
			client := httpClient()
			client.Transport = roundTrip(func(req *http.Request) (*http.Response, error) {
				calls++
				body := string(keys)
				status := 200
				switch req.URL.String() {
				case tokenURL:
					if req.Method != "POST" || req.ParseForm() != nil || len(req.PostForm) != 6 ||
						req.PostForm.Get("username") != holonetUsername || req.PostForm.Get("password") != "synthetic-password" ||
						req.PostForm.Get("client_id") != holonetClientID || req.PostForm.Get("resource") != holonetResource ||
						req.PostForm.Get("scope") != holonetScope || req.PostForm.Get("grant_type") != "client_credentials" {
						t.Fatal("exchange escaped fixed contract")
					}
					result := map[string]any{"access_token": token, "token_type": "Bearer", "expires_in": 300, "scope": holonetScope}
					if variant == "scope" {
						result["scope"] = "holonet.curate"
					}
					if variant == "refresh" {
						result["refresh_token"] = "private-value"
					}
					b, _ := json.Marshal(result)
					body = string(b)
					if variant == "status" {
						status = 400
						body = "synthetic-password"
					}
					if variant == "oversized" {
						body = strings.Repeat("x", 32769)
					}
				case holonetJWKSURL:
					if req.Method != "GET" || req.Header.Get("Authorization") != "" {
						t.Fatal("credential leaked to public keys")
					}
					if variant == "wrong-jwks" {
						body = `{"keys":[]}`
					}
				default:
					t.Fatal("unapproved endpoint")
				}
				return &http.Response{StatusCode: status, Body: io.NopCloser(strings.NewReader(body)), Header: http.Header{}}, nil
			})
			got, e := acquireHolonet(context.Background(), client, "synthetic-password", func() time.Time { return time.Unix(2000000000, 0) })
			if variant == "valid" {
				if e != nil || got != token || calls != 2 {
					t.Fatal("valid exchange failed")
				}
			} else if e == nil || got != "" || e.Error() != denied.Error() {
				t.Fatal("unsafe failed exchange output")
			}
		})
	}
}
