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

func acquirePurposeClaims(original map[string]any, purpose string) map[string]any {
	c := make(map[string]any, len(original))
	for k, v := range original {
		c[k] = v
	}
	contract := holonetAcquireContract(purpose)
	c["scope"], c["holonet_namespace"] = contract.scope, contract.namespace
	c["holonet_actions"], c["holonet_catalog_users"] = contract.actions, []string{}
	return c
}

func TestHolonetAcquirePurposesSignedAndDisjoint(t *testing.T) {
	key, keys, reader := holonetFixture(t)
	for _, purpose := range []string{"read", "start", "media"} {
		contract := holonetAcquireContract(purpose)
		claims := acquirePurposeClaims(reader, purpose)
		check := func(c map[string]any) error {
			return validateHolonetFor(signed(t, key, c), keys, 2000000000, 2000000000, 300, contract)
		}
		if check(claims) != nil {
			t.Fatal("exact purpose refused", purpose)
		}
		for _, other := range []string{"read", "start", "media"} {
			if other != purpose && check(acquirePurposeClaims(reader, other)) == nil {
				t.Fatal("purpose union", purpose, other)
			}
		}
		if check(reader) == nil || check(seedJoinClaims(reader)) == nil || check(torrentClaims(reader)) == nil {
			t.Fatal("old token admitted")
		}
		for field, value := range map[string]any{
			"scope":                 contract.scope + " holonet.torrents",
			"holonet_actions":       []string{"janitor.acquire.read", "janitor.acquire.start", "janitor.acquire.media"},
			"holonet_libraries":     []string{"3", "615"},
			"holonet_catalog_users": []string{holonetUser},
			"holonet_history_users": []string{holonetUser},
			"holonet_target_users":  []string{holonetUser},
			"holonet_acquire":       map[string]any{"library": "3"},
			"iss":                   ovIssuer, "aud": resource, "azp": "foreign", "exp": 1999999999,
		} {
			c := acquirePurposeClaims(reader, purpose)
			c[field] = value
			if check(c) == nil {
				t.Fatal("drift admitted", purpose, field)
			}
		}
		mode := "holonet-acquire-" + purpose
		if selectMode([]string{mode, "laptop"}) != mode {
			t.Fatal("closed mode")
		}
		for _, args := range [][]string{{mode}, {mode, "agent-a"}, {mode, "laptop", "--scope=x"}} {
			if selectMode(args) != "" {
				t.Fatal("open mode", args)
			}
		}
	}
}

func TestHolonetAcquireUsesSameCredentialAndExactExchange(t *testing.T) {
	key, keys, reader := holonetFixture(t)
	for _, purpose := range []string{"read", "start", "media"} {
		contract := holonetAcquireContract(purpose)
		token := signed(t, key, acquirePurposeClaims(reader, purpose))
		calls := 0
		client := &http.Client{Transport: roundTrip(func(r *http.Request) (*http.Response, error) {
			calls++
			switch calls {
			case 1:
				if r.URL.String() != tokenURL || r.Method != "POST" {
					t.Fatal("token route")
				}
				if err := r.ParseForm(); err != nil {
					t.Fatal(err)
				}
				want := map[string]string{"grant_type": "client_credentials", "client_id": holonetClientID,
					"username": holonetWriterUsername, "password": "synthetic-password",
					"scope": contract.scope, "resource": holonetResource}
				if len(r.Form) != len(want) {
					t.Fatal("extra form")
				}
				for k, v := range want {
					if len(r.Form[k]) != 1 || r.Form.Get(k) != v {
						t.Fatal("form", k)
					}
				}
				raw, _ := json.Marshal(map[string]any{"access_token": token, "token_type": "Bearer",
					"expires_in": 300, "scope": contract.scope})
				return &http.Response{StatusCode: 200, Header: make(http.Header), Body: io.NopCloser(strings.NewReader(string(raw)))}, nil
			case 2:
				if r.URL.String() != holonetJWKSURL || r.Method != "GET" {
					t.Fatal("key route")
				}
				return &http.Response{StatusCode: 200, Header: make(http.Header), Body: io.NopCloser(strings.NewReader(string(keys)))}, nil
			default:
				t.Fatal("retry")
				return nil, denied
			}
		})}
		got, err := acquireHolonetFor(context.Background(), client, "synthetic-password",
			func() time.Time { return time.Unix(2000000000, 0) }, contract)
		if err != nil || got != token || calls != 2 {
			t.Fatal("fixed acquisition", purpose, err, calls)
		}
	}
}
