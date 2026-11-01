package main

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"reflect"
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

const holonetTestOwner = `"owner":"chaldea-fleet-config holonet recommendations"`

func historyPolicy(t *testing.T, history string) holonetWriterPolicy {
	t.Helper()
	data := `{"version":1,` + holonetTestOwner + `,"target_users":["` + strings.Repeat("c", 32) + `","` +
		strings.Repeat("b", 32) + `"],"history_users":` + history + `}`
	policy, err := parseHolonetWriterPolicy([]byte(data))
	if err != nil {
		t.Fatal("valid history policy refused", history)
	}
	return policy
}
func writerClaims(reader map[string]any, contract holonetContract) map[string]any {
	claims := map[string]any{}
	for k, v := range reader {
		claims[k] = v
	}
	claims["scope"] = holonetWriterScope
	claims["holonet_namespace"] = contract.namespace
	claims["holonet_actions"] = contract.actions
	claims["holonet_target_users"] = contract.targets
	claims["holonet_history_users"] = contract.history
	return claims
}
func TestHolonetWriterHistoryPolicyIsExplicitBoundedSubset(t *testing.T) {
	b, c := strings.Repeat("b", 32), strings.Repeat("c", 32)
	old := holonetRecommendationContract(writerPolicy(t))
	if !reflect.DeepEqual(holonetRecommendationContract(historyPolicy(t, `[]`)), old) {
		t.Fatal("explicit empty history changed the writer contract")
	}
	if len(old.history) != 0 || !reflect.DeepEqual(old.actions, holonetWriterActions) {
		t.Fatal("absent history changed the writer contract")
	}
	one := holonetRecommendationContract(historyPolicy(t, `["`+b+`"]`))
	if !reflect.DeepEqual(one.history, []string{b}) || !reflect.DeepEqual(one.targets, []string{b, c}) ||
		!reflect.DeepEqual(one.actions, append(append([]string{}, holonetWriterActions...), "history.read")) {
		t.Fatal("history contract is not the exact old tuple plus history.read")
	}
	if len(holonetWriterActions) != 7 || holonetWriterActions[6] != "object.delete" {
		t.Fatal("shared writer action tuple mutated")
	}
	both := holonetRecommendationContract(historyPolicy(t, `["`+c+`","`+b+`"]`))
	if !reflect.DeepEqual(both.history, []string{b, c}) {
		t.Fatal("history order not normalized")
	}
	prefix := `{"version":1,` + holonetTestOwner + `,"target_users":["` + b + `","` + c + `"]`
	for _, tail := range []string{
		`,"history_users":null}`, `,"history_users":"` + b + `"}`, `,"history_users":{}}`,
		`,"history_users":["` + strings.Repeat("d", 32) + `"]}`, `,"history_users":["` + b + `","` + b + `"]}`,
		`,"history_users":["B` + strings.Repeat("b", 31) + `"]}`, `,"history_users":["*"]}`, `,"history_users":[3]}`,
		`,"History_users":["` + b + `"]}`, `,"history_users":["` + b + `"],"extra":true}`,
		`,"history_users":["` + b + `"],"history_users":["` + c + `"]}`, `,"userdata":["` + b + `"]}`,
	} {
		if _, err := parseHolonetWriterPolicy([]byte(prefix + tail)); err == nil {
			t.Fatal("invalid history policy accepted", tail)
		}
	}
}
func TestHolonetWriterSignedHistoryMustEqualPolicyHistory(t *testing.T) {
	key, keys, reader := holonetFixture(t)
	b, c := strings.Repeat("b", 32), strings.Repeat("c", 32)
	contract := holonetRecommendationContract(historyPolicy(t, `["`+b+`"]`))
	old := holonetRecommendationContract(writerPolicy(t))
	check := func(claims map[string]any, contract holonetContract) error {
		return validateHolonetFor(signed(t, key, claims), keys, 2000000000, 2000000000, 300, contract)
	}
	valid := writerClaims(reader, contract)
	if check(valid, contract) != nil {
		t.Fatal("exact history writer refused")
	}
	oldValid := writerClaims(reader, old)
	if check(oldValid, old) != nil || check(valid, old) == nil || check(oldValid, contract) == nil {
		t.Fatal("old and history writer contracts crossed")
	}
	// The ordinary reader keeps strict empty history and catalog.read only.
	if validateHolonet(signed(t, key, valid), keys, 2000000000, 2000000000, 300) == nil {
		t.Fatal("reader admitted a history grant")
	}
	readerHistory := map[string]any{}
	for k, v := range reader {
		readerHistory[k] = v
	}
	readerHistory["holonet_actions"] = []string{"catalog.read", "history.read"}
	readerHistory["holonet_history_users"] = []string{holonetUser}
	if validateHolonet(signed(t, key, readerHistory), keys, 2000000000, 2000000000, 300) == nil {
		t.Fatal("reader admitted history.read")
	}
	actions := append([]string{}, holonetWriterActions...)
	for _, tc := range []struct {
		field string
		value any
	}{
		{"holonet_actions", holonetWriterActions}, {"holonet_actions", append([]string{"history.read"}, actions...)},
		{"holonet_actions", append(append([]string{}, contract.actions...), "history.read")},
		{"holonet_actions", append(append([]string{}, contract.actions...), "userdata.read")},
		{"holonet_actions", append(append([]string{}, actions[:6]...), "history.read", "object.delete")},
		{"holonet_history_users", []string{}}, {"holonet_history_users", nil}, {"holonet_history_users", []string{b, b}},
		{"holonet_history_users", []string{b, c}}, {"holonet_history_users", []string{c}},
		{"holonet_history_users", []string{strings.Repeat("d", 32)}}, {"holonet_history_users", []string{"B" + b[1:]}},
		{"holonet_history_users", []string{"*"}}, {"holonet_history_users", b},
		{"holonet_target_users", []string{b}}, {"holonet_libraries", []string{"3", "4"}},
		{"holonet_catalog_users", []string{c}}, {"scope", holonetWriterScope + " holonet.history"},
	} {
		claims := map[string]any{}
		for k, v := range valid {
			claims[k] = v
		}
		claims[tc.field] = tc.value
		if check(claims, contract) == nil {
			t.Fatalf("history mismatch accepted: %s %v", tc.field, tc.value)
		}
	}
	missing := map[string]any{}
	for k, v := range valid {
		missing[k] = v
	}
	delete(missing, "holonet_history_users")
	if check(missing, contract) == nil {
		t.Fatal("missing history accepted")
	}
	// Ordering is immaterial for an exact two-recipient history set.
	two := holonetRecommendationContract(historyPolicy(t, `["`+b+`","`+c+`"]`))
	permuted := writerClaims(reader, two)
	permuted["holonet_history_users"] = []string{c, b}
	if check(permuted, two) != nil {
		t.Fatal("history permutation refused")
	}
}
func TestHolonetWriterHistoryExchangeKeepsFixedRequest(t *testing.T) {
	key, keys, reader := holonetFixture(t)
	contract := holonetRecommendationContract(historyPolicy(t, `["`+strings.Repeat("c", 32)+`"]`))
	token := signed(t, key, writerClaims(reader, contract))
	calls := 0
	client := httpClient()
	client.Transport = roundTrip(func(req *http.Request) (*http.Response, error) {
		calls++
		body := string(keys)
		switch req.URL.String() {
		case tokenURL:
			// History adds no form field, scope, user or recipient selector.
			if req.Method != "POST" || req.ParseForm() != nil || len(req.PostForm) != 6 ||
				req.PostForm.Get("grant_type") != "client_credentials" || req.PostForm.Get("username") != holonetWriterUsername ||
				req.PostForm.Get("password") != "synthetic-writer-password" || req.PostForm.Get("scope") != holonetWriterScope ||
				req.PostForm.Get("resource") != holonetResource || req.PostForm.Get("client_id") != holonetClientID {
				t.Fatal("history writer exchange escaped fixed tuple")
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
	now := func() time.Time { return time.Unix(2000000000, 0) }
	got, err := acquireHolonetFor(context.Background(), client, "synthetic-writer-password", now, contract)
	if err != nil || got != token || calls != 2 {
		t.Fatal("history writer exchange failed")
	}
	// The same signed history token is refused for the old writer policy.
	if got, err := acquireHolonetFor(context.Background(), client, "synthetic-writer-password", now,
		holonetRecommendationContract(writerPolicy(t))); err == nil || got != "" || calls != 4 {
		t.Fatal("old writer admitted a history token")
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
