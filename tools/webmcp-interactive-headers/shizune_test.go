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

func TestShizuneSignedContract(t *testing.T) {
	key, jwks, c := fixture(t)
	c = map[string]any{"iss": shizuneIssuer, "aud": shizuneResource, "azp": shizuneClientID, "scope": shizuneScope,
		"sub": "fixture", "shizune_owner": "igor", "iat": int64(2000000000), "exp": int64(2000000300)}
	check := func(c map[string]any) error {
		return validateShizune(signed(t, key, c), jwks, 2000000000, 2000000000, 300)
	}
	if check(c) != nil {
		t.Fatal("valid token refused")
	}
	for field, value := range map[string]any{"iss": issuer, "aud": resource, "azp": clientID, "scope": "shizune.other", "shizune_owner": "other", "exp": int64(2000000301), "iat": int64(1999999990), "nbf": int64(2000000001), "sub": "", "ov_actions": []string{"read"}, "holonet_actions": []string{"read"}, "jocasta_operator": true, "grants": nil, "project": "other", "source": "other", "webmcp_identity": "other", "homelab_hosts": []string{}, "ha_actions": []string{}, "SHIZUNE_OWNER": "igor", "ſcope": shizuneScope, "shizune_other": true} {
		t.Run(field, func(t *testing.T) {
			bad := copyClaims(c)
			bad[field] = value
			if check(bad) == nil {
				t.Fatal("invalid claim admitted")
			}
		})
	}
	for _, field := range []string{"iss", "aud", "azp", "scope", "shizune_owner", "iat", "exp"} {
		bad := copyClaims(c)
		delete(bad, field)
		if check(bad) == nil {
			t.Fatal("missing claim admitted", field)
		}
	}
	for _, alg := range []string{"none", "HS256", "RS512"} {
		if validateShizune(signedWith(t, key, map[string]any{"alg": alg, "kid": "fixture"}, c), jwks, 2000000000, 2000000000, 300) == nil {
			t.Fatal("wrong alg admitted")
		}
	}
	token := signed(t, key, c)
	parts := strings.Split(token, ".")
	parts[1] = encoded(map[string]any{"shizune_owner": "other"})
	if validateShizune(strings.Join(parts, "."), jwks, 2000000000, 2000000000, 300) == nil {
		t.Fatal("tamper admitted")
	}
	dup := strings.TrimSuffix(string(mustJSON(t, c)), "}") + `,"shizune_owner":"igor"}`
	if validateShizune(signedRaw(t, key, dup), jwks, 2000000000, 2000000000, 300) == nil {
		t.Fatal("duplicate admitted")
	}
}

func TestShizuneClosedExchange(t *testing.T) {
	key, jwks, _ := fixture(t)
	c := map[string]any{"iss": shizuneIssuer, "aud": shizuneResource, "azp": shizuneClientID, "scope": shizuneScope, "sub": "fixture", "shizune_owner": "igor", "iat": 2000000000, "exp": 2000000300}
	token := signed(t, key, c)
	for host, binding := range ovFullHosts {
		if selectMode([]string{"shizune", host}) != "shizune" || ovFullBinding(host, binding.node, binding.uid) != nil {
			t.Fatal("binding refused")
		}
		if ovFullBinding(host, binding.node, 0) == nil || ovFullBinding(host, "wrong", binding.uid) == nil {
			t.Fatal("wrong binding admitted")
		}
		client := httpClient()
		calls := 0
		client.Transport = roundTrip(func(r *http.Request) (*http.Response, error) {
			calls++
			body := string(jwks)
			if r.URL.String() == tokenURL {
				if r.Method != "POST" || r.ParseForm() != nil {
					t.Fatal("bad request")
				}
				f := r.PostForm
				if len(f) != 5 || f.Get("grant_type") != "client_credentials" || f.Get("client_id") != shizuneClientID || f.Get("username") != "chaldea-"+host+"-shizune-interactive" || f.Get("password") != "fixture-password" || f.Get("scope") != shizuneScope {
					t.Fatal("exchange drift")
				}
				b, _ := json.Marshal(map[string]any{"access_token": token, "token_type": "Bearer", "expires_in": 300, "scope": shizuneScope})
				body = string(b)
			} else if r.URL.String() != shizuneJWKSURL || r.Method != "GET" {
				t.Fatal("unapproved endpoint")
			}
			return &http.Response{StatusCode: 200, Body: io.NopCloser(strings.NewReader(body)), Header: http.Header{}}, nil
		})
		got, err := acquireShizune(context.Background(), client, host, "fixture-password", func() time.Time { return time.Unix(2000000000, 0) })
		if err != nil || got != token || calls != 2 {
			t.Fatal("exchange refused")
		}
	}
	for _, args := range [][]string{{"shizune"}, {"shizune", "agent-a"}, {"shizune", "laptop", "extra"}, {"SHIZUNE", "laptop"}, {"shizune", "--host=laptop"}} {
		if selectMode(args) != "" {
			t.Fatal("open tuple admitted")
		}
	}
	if ovFullBinding("agent-a", "agent-a", 1000) == nil {
		t.Fatal("foreign host admitted")
	}
}
