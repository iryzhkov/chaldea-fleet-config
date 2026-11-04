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

func janitorClaims(reader map[string]any) map[string]any {
	c := map[string]any{}
	for k, v := range reader {
		c[k] = v
	}
	contract := holonetJanitorContract()
	c["scope"] = contract.scope
	c["holonet_namespace"] = contract.namespace
	c["holonet_actions"] = contract.actions
	c["holonet_catalog_users"] = []string{}
	return c
}

func TestHolonetJanitorSignedReadBoundary(t *testing.T) {
	key, keys, reader := holonetFixture(t)
	contract := holonetJanitorContract()
	valid := janitorClaims(reader)
	check := func(c map[string]any) error {
		return validateHolonetFor(signed(t, key, c), keys, 2000000000, 2000000000, 300, contract)
	}
	for _, scope := range []string{holonetJanitorScope, "holonet.janitor holonet.read"} {
		valid["scope"] = scope
		if check(valid) != nil {
			t.Fatal("exact janitor refused")
		}
	}
	if validateHolonet(signed(t, key, valid), keys, 2000000000, 2000000000, 300) == nil ||
		validateHolonetFor(signed(t, key, valid), keys, 2000000000, 2000000000, 300, holonetRecommendationContract(writerPolicy(t))) == nil ||
		check(reader) == nil {
		t.Fatal("contracts crossed")
	}
	for _, tc := range []struct {
		field string
		value any
	}{
		{"scope", holonetWriterScope}, {"scope", holonetJanitorScope + " holonet.home"},
		{"scope", "holonet.janitor holonet.janitor"}, {"scope", "holonet.read  holonet.janitor"},
		{"holonet_namespace", "managed-recommendations"}, {"holonet_libraries", []string{"3", "615"}},
		{"holonet_catalog_users", []string{holonetUser}}, {"holonet_target_users", []string{holonetUser}},
		{"holonet_history_users", []string{holonetUser}}, {"holonet_actions", []string{"janitor.importers.read"}},
		{"holonet_actions", []string{"janitor.importers.read", "janitor.custody.read", "janitor.importers.pause"}},
		{"holonet_janitor", map[string]any{"library": "3"}}, {"holonet_catalog_users", nil},
		{"iss", ovIssuer}, {"aud", resource}, {"azp", "other"}, {"exp", 1999999999},
	} {
		c := map[string]any{}
		for k, v := range valid {
			c[k] = v
		}
		c[tc.field] = tc.value
		if check(c) == nil {
			t.Fatalf("accepted drift: %s", tc.field)
		}
	}
	if selectMode([]string{"holonet-janitor", "laptop"}) != "holonet-janitor" {
		t.Fatal("tuple refused")
	}
	for _, args := range [][]string{{"holonet-janitor"}, {"holonet-janitor", "agent-a"}, {"holonet-janitor", "laptop", "extra"}} {
		if selectMode(args) != "" {
			t.Fatal("open tuple")
		}
	}
}

func TestHolonetJanitorUsesExistingAccountAndFixedExchange(t *testing.T) {
	key, keys, reader := holonetFixture(t)
	token := signed(t, key, janitorClaims(reader))
	calls := 0
	client := &http.Client{Transport: roundTrip(func(r *http.Request) (*http.Response, error) {
		calls++
		switch calls {
		case 1:
			if r.URL.String() != tokenURL || r.Method != "POST" {
				t.Fatal("foreign token route")
			}
			if err := r.ParseForm(); err != nil {
				t.Fatal(err)
			}
			want := map[string]string{"grant_type": "client_credentials", "client_id": holonetClientID, "username": holonetWriterUsername,
				"password": "synthetic-password", "scope": holonetJanitorScope, "resource": holonetResource}
			if len(r.Form) != len(want) {
				t.Fatal("extra form fields")
			}
			for k, v := range want {
				if len(r.Form[k]) != 1 || r.Form.Get(k) != v {
					t.Fatalf("wrong %s", k)
				}
			}
			raw, _ := json.Marshal(map[string]any{"access_token": token, "token_type": "Bearer", "expires_in": 300, "scope": holonetJanitorScope})
			return &http.Response{StatusCode: 200, Body: io.NopCloser(strings.NewReader(string(raw))), Header: make(http.Header)}, nil
		case 2:
			if r.URL.String() != holonetJWKSURL || r.Method != "GET" {
				t.Fatal("foreign key route")
			}
			return &http.Response{StatusCode: 200, Body: io.NopCloser(strings.NewReader(string(keys))), Header: make(http.Header)}, nil
		default:
			t.Fatal("retry")
			return nil, denied
		}
	})}
	got, err := acquireHolonetFor(context.Background(), client, "synthetic-password", func() time.Time { return time.Unix(2000000000, 0) }, holonetJanitorContract())
	if err != nil || got != token || calls != 2 {
		t.Fatal("fixed acquisition failed", err, calls)
	}
}
