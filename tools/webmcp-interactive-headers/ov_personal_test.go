package main

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"strings"
	"testing"
	"time"
)

func personalFixture(actions []string) map[string]any {
	return map[string]any{"account": "default", "user": "default", "actions": actions}
}

func personalScope(actions []string) string {
	scope := ovFullScopes
	for _, action := range actions {
		scope += " ov.personal." + action
	}
	return scope
}

func TestOVPersonalSignedContract(t *testing.T) {
	key, jwks, old := ovFullFixture(t)
	check := func(c map[string]any) error {
		return validateOVFull(signed(t, key, c), jwks, 2000000000, 2000000000, 300)
	}
	if check(old) != nil {
		t.Fatal("old resources-only full token refused")
	}
	// Every nonempty canonical subset is valid, with exactly its own scopes.
	for mask := 1; mask < 1<<len(ovPersonalActions); mask++ {
		var actions []string
		for i, action := range ovPersonalActions {
			if mask&(1<<i) != 0 {
				actions = append(actions, action)
			}
		}
		c := copyClaims(old)
		c["ov_personal"] = personalFixture(actions)
		c["scope"] = personalScope(actions)
		if check(c) != nil {
			t.Fatalf("canonical subset refused: %v", actions)
		}
	}
	valid := copyClaims(old)
	valid["ov_personal"] = personalFixture(ovPersonalActions)
	valid["scope"] = ovFullRequestScopes
	for name, grant := range map[string]any{
		"null": nil, "string": "default", "list": []string{"default"},
		"empty":           map[string]any{},
		"missing-account": map[string]any{"user": "default", "actions": ovPersonalActions},
		"foreign-account": map[string]any{"account": "other", "user": "default", "actions": ovPersonalActions},
		"foreign-user":    map[string]any{"account": "default", "user": "other", "actions": ovPersonalActions},
		"owner-type":      map[string]any{"account": true, "user": "default", "actions": ovPersonalActions},
		"extra":           map[string]any{"account": "default", "user": "default", "actions": ovPersonalActions, "admin": true},
		"null-actions":    personalFixture(nil), "empty-actions": personalFixture([]string{}),
		"unknown-action": personalFixture([]string{"memory.delete"}),
		"duplicate":      personalFixture([]string{"memory.read", "memory.read"}),
		"reordered":      personalFixture([]string{"session.read", "memory.read"}),
		"too-many":       personalFixture(append(append([]string{}, ovPersonalActions...), "memory.read")),
		"string-actions": map[string]any{"account": "default", "user": "default", "actions": "memory.read"},
		"numeric-action": map[string]any{"account": "default", "user": "default", "actions": []any{1}},
	} {
		t.Run(name, func(t *testing.T) {
			c := copyClaims(valid)
			c["ov_personal"] = grant
			if check(c) == nil {
				t.Fatal("malformed personal grant admitted")
			}
		})
	}
	for name, scope := range map[string]string{
		"missing-action-scope": ovFullScopes,
		"unclaimed-scope":      personalScope([]string{"memory.read", "memory.write"}),
		"unknown-scope":        ovFullRequestScopes + " ov.personal.admin",
		"duplicate-scope":      ovFullRequestScopes + " ov.personal.memory.read",
		"missing-resource":     strings.Replace(ovFullRequestScopes, "ov.remove ", "", 1),
	} {
		c := copyClaims(valid)
		c["ov_personal"] = personalFixture([]string{"memory.read"})
		c["scope"] = scope
		if check(c) == nil {
			t.Fatalf("%s admitted", name)
		}
	}
	unclaimed := copyClaims(old)
	unclaimed["scope"] = ovFullRequestScopes
	if check(unclaimed) == nil {
		t.Fatal("personal scopes without signed claim admitted")
	}
	folded := copyClaims(old)
	folded["OV_PERSONAL"] = personalFixture(ovPersonalActions)
	if check(folded) == nil {
		t.Fatal("folded personal claim admitted")
	}
	_, _, narrow := ovFixture(t)
	narrow["ov_personal"] = personalFixture([]string{"memory.read"})
	if validateOV(signed(t, key, narrow), jwks, 2000000000, 2000000000, 300) == nil {
		t.Fatal("narrow token admitted personal claim")
	}
	// Duplicate object keys remain forbidden even under a valid signature.
	raw := strings.Replace(string(mustJSON(t, valid)), `"account":"default"`, `"account":"default","account":"default"`, 1)
	if validateOVFull(signedRaw(t, key, raw), jwks, 2000000000, 2000000000, 300) == nil {
		t.Fatal("duplicate personal key admitted")
	}
	// Personal authority cannot bypass existing issuer, client, subject or lifetime checks.
	for field, value := range map[string]any{"iss": issuer, "aud": resource, "azp": clientID, "sub": "", "exp": 1999999999, "ov_namespaces": []string{"viking://user"}} {
		c := copyClaims(valid)
		c[field] = value
		if check(c) == nil {
			t.Fatalf("personal token bypassed %s", field)
		}
	}
}

// A rejecting legacy issuer is surfaced, never hidden by a second exchange.
func TestOVPersonalLegacyIssuerRejection(t *testing.T) {
	client := httpClient()
	calls := 0
	client.Transport = roundTrip(func(req *http.Request) (*http.Response, error) {
		calls++
		if req.URL.String() != tokenURL || req.ParseForm() != nil ||
			req.PostForm.Get("scope") != ovFullRequestScopes {
			t.Fatal("unexpected legacy issuer request")
		}
		return &http.Response{StatusCode: 400, Body: io.NopCloser(strings.NewReader(`{"error":"invalid_scope"}`)), Header: http.Header{}}, nil
	})
	got, err := acquireOVFull(context.Background(), client, "laptop", "FixtureOnly", time.Now)
	if got != "" || err != denied || calls != 1 {
		t.Fatal("legacy rejection bypassed or retried")
	}
}

func TestOVPersonalExchange(t *testing.T) {
	key, jwks, old := ovFullFixture(t)
	for _, host := range []string{"laptop", "omarchy-pc"} {
		for _, actions := range [][]string{nil, ovPersonalActions, {"memory.read", "session.read"}} {
			c := copyClaims(old)
			scope := ovFullScopes
			if len(actions) != 0 {
				scope = personalScope(actions)
				c["scope"] = scope
				c["ov_personal"] = personalFixture(actions)
			}
			token := signed(t, key, c)
			calls := 0
			client := httpClient()
			client.Transport = roundTrip(func(req *http.Request) (*http.Response, error) {
				calls++
				body := string(jwks)
				if req.URL.String() == tokenURL {
					if req.ParseForm() != nil || req.PostForm.Get("scope") != ovFullRequestScopes ||
						req.PostForm.Get("username") != "chaldea-"+host+"-ov-full-interactive" ||
						req.Header.Get("X-OpenViking-User") != "" {
						t.Fatal("personal request contract drift")
					}
					data, _ := json.Marshal(map[string]any{"access_token": token, "token_type": "Bearer", "expires_in": 300, "scope": scope})
					body = string(data)
				} else if req.URL.String() != ovJWKSURL {
					t.Fatal("unexpected endpoint")
				}
				return &http.Response{StatusCode: 200, Body: io.NopCloser(strings.NewReader(body)), Header: http.Header{}}, nil
			})
			got, err := acquireOVFull(context.Background(), client, host, "FixtureOnly", func() time.Time { return time.Unix(2000000000, 0) })
			if err != nil || got != token || calls != 2 {
				t.Fatal("old/full/reduced personal exchange failed")
			}
		}
	}
}
