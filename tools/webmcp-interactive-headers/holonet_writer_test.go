package main

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func writerPolicy(t *testing.T) holonetWriterPolicy {
	t.Helper()
	raw, _ := json.Marshal(holonetWriterPolicy{Version: 1, Owner: holonetWriterPolicyOwner, Targets: []string{strings.Repeat("b", 32), strings.Repeat("c", 32)}})
	policy, err := parseHolonetWriterPolicy(raw)
	if err != nil {
		t.Fatal(err)
	}
	return policy
}
func TestHolonetWriterExactCohortAndSignedScopes(t *testing.T) {
	key, keys, reader := holonetFixture(t)
	contract := holonetRecommendationContract(writerPolicy(t))
	valid := map[string]any{}
	for k, v := range reader {
		valid[k] = v
	}
	valid["scope"] = holonetWriterScope
	valid["holonet_namespace"] = "managed-recommendations"
	valid["holonet_actions"] = holonetWriterActions
	valid["holonet_target_users"] = contract.targets
	check := func(claims map[string]any) error {
		return validateHolonetFor(signed(t, key, claims), keys, 2000000000, 2000000000, 300, contract)
	}
	for _, scope := range []string{"holonet.read holonet.curate holonet.home", "holonet.curate holonet.home holonet.read", "holonet.home holonet.read holonet.curate"} {
		valid["scope"] = scope
		if check(valid) != nil {
			t.Fatal("exact writer refused")
		}
	}
	valid["scope"] = holonetWriterScope
	if validateHolonet(signed(t, key, valid), keys, 2000000000, 2000000000, 300) == nil || check(reader) == nil {
		t.Fatal("reader/writer contract crossed")
	}
	for _, tc := range []struct {
		field string
		value any
	}{
		{"scope", "holonet.read"}, {"scope", "holonet.read holonet.curate"}, {"scope", holonetWriterScope + " holonet.admin"},
		{"scope", "holonet.read holonet.read holonet.home"}, {"scope", "holonet.read  holonet.curate holonet.home"},
		{"holonet_target_users", []string{}}, {"holonet_target_users", nil},
		{"holonet_target_users", []string{contract.targets[0], contract.targets[0]}},
		{"holonet_target_users", []string{contract.targets[0], strings.Repeat("d", 32)}},
		{"holonet_actions", holonetWriterActions[:6]}, {"holonet_actions", append(append([]string{}, holonetWriterActions...), "media.delete")},
		{"holonet_namespace", "movies-catalog"}, {"holonet_history_users", []string{holonetUser}},
		{"holonet_libraries", []string{"3", "4"}}, {"holonet_catalog_users", []string{strings.Repeat("d", 32)}},
	} {
		copy := map[string]any{}
		for k, v := range valid {
			copy[k] = v
		}
		copy[tc.field] = tc.value
		if check(copy) == nil {
			t.Fatalf("widened/partial writer accepted: %s", tc.field)
		}
	}
	valid["holonet_target_users"] = []string{contract.targets[1], contract.targets[0]}
	if check(valid) != nil {
		t.Fatal("same cohort permutation refused")
	}
	if selectMode([]string{"holonet-writer", "laptop"}) != "holonet-writer" {
		t.Fatal("closed tuple refused")
	}
	for _, args := range [][]string{{"holonet-writer"}, {"holonet-writer", "agent-a"}, {"holonet-writer", "omarchy-pc"}, {"holonet-writer", "laptop", "extra"}} {
		if selectMode(args) != "" {
			t.Fatal("open tuple accepted")
		}
	}
}
func TestHolonetWriterPublicPolicyIsClosedAndRootOwned(t *testing.T) {
	policy := writerPolicy(t)
	raw, _ := json.Marshal(policy)
	for _, data := range [][]byte{
		[]byte(`{}`), []byte(`{"version":true}`), append(raw, []byte(" {}")...),
		[]byte(`{"Version":1,"owner":"chaldea-fleet-config holonet recommendations","target_users":["bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"]}`),
		[]byte(`{"version":1,"owner":"foreign","target_users":["bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"]}`),
		[]byte(`{"version":1,"owner":"chaldea-fleet-config holonet recommendations","target_users":[]}`),
	} {
		if _, err := parseHolonetWriterPolicy(data); err == nil {
			t.Fatal("invalid policy accepted")
		}
	}
	for _, targets := range [][]string{nil, {"*"}, {"B" + strings.Repeat("b", 31)}, {policy.Targets[0], policy.Targets[0]}} {
		bad, _ := json.Marshal(holonetWriterPolicy{Version: 1, Owner: holonetWriterPolicyOwner, Targets: targets})
		if _, err := parseHolonetWriterPolicy(bad); err == nil {
			t.Fatal("invalid cohort accepted")
		}
	}
	// Namespace UID0 tests the real root-owner seam. Hosted nonroot runs still
	// exercise the signed/policy parser tests and assert foreign custody refuses.
	parent := t.TempDir()
	path := filepath.Join(parent, "policy.json")
	if err := os.WriteFile(path, raw, 0644); err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(path, 0644); err != nil {
		t.Fatal(err)
	}
	if os.Getuid() != 0 {
		if _, err := readHolonetWriterPolicy(path); err == nil {
			t.Fatal("user-owned policy accepted")
		}
		return
	}
	if _, err := readHolonetWriterPolicy(path); err != nil {
		t.Fatal("root policy refused", err)
	}
	if err := os.Chmod(path, 0664); err != nil {
		t.Fatal(err)
	}
	if _, err := readHolonetWriterPolicy(path); err == nil {
		t.Fatal("writable policy accepted")
	}
	if err := os.Chmod(path, 0644); err != nil {
		t.Fatal(err)
	}
	link := filepath.Join(parent, "link")
	if err := os.Symlink(path, link); err != nil {
		t.Fatal(err)
	}
	if _, err := readHolonetWriterPolicy(link); err == nil {
		t.Fatal("policy link accepted")
	}
	if err := os.Remove(link); err != nil {
		t.Fatal(err)
	}
	if err := os.Link(path, link); err != nil {
		t.Fatal(err)
	}
	if _, err := readHolonetWriterPolicy(path); err == nil {
		t.Fatal("hardlinked policy accepted")
	}
}
func TestHolonetWriterExchangeUsesSeparateAccountAndFixedEndpoints(t *testing.T) {
	key, keys, claims := holonetFixture(t)
	contract := holonetRecommendationContract(writerPolicy(t))
	claims["scope"] = holonetWriterScope
	claims["holonet_namespace"] = contract.namespace
	claims["holonet_actions"] = contract.actions
	claims["holonet_target_users"] = contract.targets
	token := signed(t, key, claims)
	calls := 0
	client := httpClient()
	client.Transport = roundTrip(func(req *http.Request) (*http.Response, error) {
		calls++
		body := string(keys)
		switch req.URL.String() {
		case tokenURL:
			if req.Method != "POST" || req.ParseForm() != nil || len(req.PostForm) != 6 ||
				req.PostForm.Get("username") != holonetWriterUsername || req.PostForm.Get("password") != "synthetic-writer-password" ||
				req.PostForm.Get("scope") != holonetWriterScope || req.PostForm.Get("resource") != holonetResource ||
				req.PostForm.Get("client_id") != holonetClientID {
				t.Fatal("writer exchange escaped fixed tuple")
			}
			raw, _ := json.Marshal(map[string]any{"access_token": token, "token_type": "Bearer", "expires_in": 300, "scope": holonetWriterScope})
			body = string(raw)
		case holonetJWKSURL:
			if req.Method != "GET" || req.Header.Get("Authorization") != "" {
				t.Fatal("credential leaked to keys")
			}
		default:
			t.Fatal("unapproved endpoint")
		}
		return &http.Response{StatusCode: 200, Body: io.NopCloser(strings.NewReader(body)), Header: http.Header{}}, nil
	})
	got, err := acquireHolonetFor(context.Background(), client, "synthetic-writer-password", func() time.Time { return time.Unix(2000000000, 0) }, contract)
	if err != nil || got != token || calls != 2 {
		t.Fatal("writer exchange failed")
	}
	if holonetWriterCredential == holonetCredential || holonetWriterUsername == holonetUsername {
		t.Fatal("reader credential reused")
	}
}
