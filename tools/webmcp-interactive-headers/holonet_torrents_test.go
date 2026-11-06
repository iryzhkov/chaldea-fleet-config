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

func torrentClaims(reader map[string]any) map[string]any {
	c := map[string]any{}
	for k, v := range reader {
		c[k] = v
	}
	contract := holonetTorrentsContract()
	c["scope"] = contract.scope
	c["holonet_namespace"] = contract.namespace
	c["holonet_actions"] = contract.actions
	c["holonet_catalog_users"] = []string{}
	return c
}

func TestHolonetTorrentsSignedReadBoundary(t *testing.T) {
	key, keys, reader := holonetFixture(t)
	contract := holonetTorrentsContract()
	valid := torrentClaims(reader)
	check := func(c map[string]any) error {
		return validateHolonetFor(signed(t, key, c), keys, 2000000000, 2000000000, 300, contract)
	}
	for _, scope := range []string{holonetTorrentsScope, "holonet.torrents holonet.janitor holonet.read"} {
		valid["scope"] = scope
		if check(valid) != nil {
			t.Fatal("exact janitor refused")
		}
	}
	if validateHolonet(signed(t, key, valid), keys, 2000000000, 2000000000, 300) == nil ||
		validateHolonetFor(signed(t, key, valid), keys, 2000000000, 2000000000, 300, holonetRecommendationContract(writerPolicy(t))) == nil ||
		check(reader) == nil ||
		validateHolonetFor(signed(t, key, valid), keys, 2000000000, 2000000000, 300, holonetJanitorContract()) == nil ||
		check(janitorClaims(reader)) == nil {
		t.Fatal("contracts crossed")
	}
	for _, tc := range []struct {
		field string
		value any
	}{
		{"scope", holonetJanitorScope}, {"scope", holonetWriterScope}, {"scope", holonetTorrentsScope + " holonet.home"},
		{"scope", "holonet.janitor holonet.janitor"}, {"scope", "holonet.read  holonet.janitor"},
		{"holonet_namespace", "managed-recommendations"}, {"holonet_libraries", []string{"3", "615"}},
		{"holonet_catalog_users", []string{holonetUser}}, {"holonet_target_users", []string{holonetUser}},
		{"holonet_history_users", []string{holonetUser}}, {"holonet_actions", []string{"janitor.importers.read", "janitor.custody.read"}},
		{"holonet_actions", []string{"janitor.torrents.read", "janitor.importers.read"}},
		{"holonet_actions", []string{"janitor.torrents.read", "janitor.torrents.read"}},
		{"holonet_actions", []string{"janitor.torrents.pause"}},
		{"holonet_libraries", []string{"615"}}, {"holonet_actions", nil},
		{"holonet_actions", []string{"janitor.importers.read", "janitor.custody.read", "janitor.importers.pause"}},
		{"holonet_torrents", map[string]any{"library": "3"}}, {"holonet_private", true}, {"holonet_janitor", map[string]any{"library": "3"}}, {"holonet_catalog_users", nil},
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
	if selectMode([]string{"holonet-torrents", "laptop"}) != "holonet-torrents" {
		t.Fatal("tuple refused")
	}
	for _, args := range [][]string{{"holonet-torrents"}, {"holonet-torrents", "agent-a"}, {"holonet-torrents", "laptop", "extra"}} {
		if selectMode(args) != "" {
			t.Fatal("open tuple")
		}
	}
}

func TestHolonetTorrentsUsesExistingAccountAndFixedExchange(t *testing.T) {
	key, keys, reader := holonetFixture(t)
	token := signed(t, key, torrentClaims(reader))
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
				"password": "synthetic-password", "scope": holonetTorrentsScope, "resource": holonetResource}
			if len(r.Form) != len(want) {
				t.Fatal("extra form fields")
			}
			for k, v := range want {
				if len(r.Form[k]) != 1 || r.Form.Get(k) != v {
					t.Fatalf("wrong %s", k)
				}
			}
			raw, _ := json.Marshal(map[string]any{"access_token": token, "token_type": "Bearer", "expires_in": 300, "scope": holonetTorrentsScope})
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
	got, err := acquireHolonetFor(context.Background(), client, "synthetic-password", func() time.Time { return time.Unix(2000000000, 0) }, holonetTorrentsContract())
	if err != nil || got != token || calls != 2 {
		t.Fatal("fixed acquisition failed", err, calls)
	}
}

func TestHolonetTorrentsResponseScopeRefusedBeforeKeys(t *testing.T) {
	for _, scope := range []string{holonetJanitorScope, holonetWriterScope, holonetTorrentsScope + " holonet.home", "", "holonet.read holonet.torrents"} {
		calls := 0
		client := &http.Client{Transport: roundTrip(func(r *http.Request) (*http.Response, error) {
			calls++
			if calls != 1 || r.URL.String() != tokenURL {
				t.Fatal("fetched keys for foreign response scope")
			}
			raw, _ := json.Marshal(map[string]any{"access_token": "synthetic", "token_type": "Bearer", "expires_in": 300, "scope": scope})
			return &http.Response{StatusCode: 200, Body: io.NopCloser(strings.NewReader(string(raw))), Header: make(http.Header)}, nil
		})}
		token, err := acquireHolonetFor(context.Background(), client, "synthetic-password", func() time.Time { return time.Unix(2000000000, 0) }, holonetTorrentsContract())
		if err == nil || token != "" || calls != 1 {
			t.Fatal("accepted response scope drift")
		}
	}
}

func TestHolonetOldJanitorContractUnchanged(t *testing.T) {
	c := holonetJanitorContract()
	raw, err := json.Marshal(c.actions)
	if err != nil || string(raw) != "[\"janitor.importers.read\",\"janitor.custody.read\"]" ||
		c.scope != "holonet.read holonet.janitor" || c.namespace != "managed-janitor" ||
		len(c.libraries) != 1 || c.libraries[0] != "3" ||
		len(c.catalog) != 0 || len(c.history) != 0 || len(c.targets) != 0 || c.username != holonetWriterUsername {
		t.Fatal("old two-action contract changed")
	}
}

func TestHolonetTorrentsClosedContractAndBinding(t *testing.T) {
	c := holonetTorrentsContract()
	if c.scope != "holonet.read holonet.janitor holonet.torrents" || c.namespace != "managed-janitor" ||
		len(c.actions) != 1 || c.actions[0] != "janitor.torrents.read" || len(c.libraries) != 1 || c.libraries[0] != "3" ||
		len(c.catalog) != 0 || len(c.history) != 0 || len(c.targets) != 0 || c.username != holonetWriterUsername {
		t.Fatal("torrent contract drift")
	}
	for _, args := range [][]string{{"holonet-torrents", "omarchy-pc"}, {"holonet-torrents", "laptop", "--scope=x"},
		{"holonet-torrents", "laptop", "--action=janitor.torrents.read"}, {"holonet-torrents", "laptop", "--header=x"},
		{"holonet-torrents", "laptop", "--resource=homelab-qbit-movies"}} {
		if selectMode(args) != "" {
			t.Fatal("caller selected grant")
		}
	}
	for _, tc := range []struct {
		node  string
		uid   int
		valid bool
	}{
		{"omarchy-macbook-air-igor", 1001, true}, {"laptop", 1001, false},
		{"omarchy-pc", 1001, false}, {"omarchy-macbook-air-igor", 1000, false},
	} {
		if (holonetBinding(tc.node, tc.uid) == nil) != tc.valid {
			t.Fatal("binding drift")
		}
	}
}
