package main

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"reflect"
	"strings"
	"testing"
	"time"
)

// The Movie/TV/anime opt-in: Movies 3 plus the two configured tvshows libraries.
var seriesLibraries = []string{"3", "615", "1132"}

func libraryPolicyJSON(extra string) string {
	return `{"version":1,` + holonetTestOwner + `,"target_users":["` + strings.Repeat("c", 32) + `","` +
		strings.Repeat("b", 32) + `"]` + extra + `}`
}
func libraryPolicy(t *testing.T, extra string) holonetWriterPolicy {
	t.Helper()
	policy, err := parseHolonetWriterPolicy([]byte(libraryPolicyJSON(extra)))
	if err != nil {
		t.Fatal("valid library policy refused", extra)
	}
	return policy
}
func libraryClaims(reader map[string]any, contract holonetContract) map[string]any {
	claims := writerClaims(reader, contract)
	claims["holonet_libraries"] = contract.libraries
	return claims
}

func TestHolonetWriterLibraryPolicyIsExplicitAndBounded(t *testing.T) {
	old := holonetRecommendationContract(writerPolicy(t))
	if !reflect.DeepEqual(old.libraries, []string{"3"}) || !reflect.DeepEqual(holonetReaderContract().libraries, []string{"3"}) {
		t.Fatal("absent library_ids changed the Movies-only contract")
	}
	// Absent and explicit ["3"] are the same writer; the absent policy keeps no field.
	if !reflect.DeepEqual(holonetRecommendationContract(libraryPolicy(t, `,"library_ids":["3"]`)), old) {
		t.Fatal("explicit Movies-only set changed the writer contract")
	}
	if raw, _ := json.Marshal(writerPolicy(t)); strings.Contains(string(raw), "library_ids") {
		t.Fatal("default policy encodes library_ids")
	}
	wide := libraryPolicy(t, `,"library_ids":["615","3","1132"]`)
	contract := holonetRecommendationContract(wide)
	if !reflect.DeepEqual(wide.Libraries, []string{"1132", "3", "615"}) || !reflect.DeepEqual(contract.libraries, wide.Libraries) ||
		!reflect.DeepEqual(contract.actions, holonetWriterActions) || len(contract.history) != 0 ||
		!reflect.DeepEqual(contract.targets, old.targets) || contract.scope != old.scope || contract.username != old.username {
		t.Fatal("library opt-in changed more than the library set")
	}
	both := holonetRecommendationContract(libraryPolicy(t, `,"history_users":["`+strings.Repeat("b", 32)+`"],"library_ids":["3","615","1132"]`))
	if !reflect.DeepEqual(both.libraries, contract.libraries) || !reflect.DeepEqual(both.history, []string{strings.Repeat("b", 32)}) ||
		!reflect.DeepEqual(both.actions, append(append([]string{}, holonetWriterActions...), holonetHistoryAction)) {
		t.Fatal("history and library opt-ins do not compose")
	}
	libraryPolicy(t, `,"library_ids":["3","615"]`)
	libraryPolicy(t, `,"library_ids":["3","9999999999"]`)
	for _, tail := range []string{
		`,"library_ids":[]`, `,"library_ids":null`, `,"library_ids":"3"`, `,"library_ids":3`, `,"library_ids":{}`,
		`,"library_ids":{"3":true}`, `,"library_ids":true`, `,"library_ids":[3,615,1132]`, `,"library_ids":["3",615]`,
		`,"library_ids":[null]`, `,"library_ids":[["3"]]`,
		`,"library_ids":["615","1132"]`, `,"library_ids":["615"]`, `,"library_ids":["3","615","1132","4"]`,
		`,"library_ids":["3","3"]`, `,"library_ids":["3","615","615"]`,
		`,"library_ids":["03","615"]`, `,"library_ids":["3","0615"]`, `,"library_ids":["3","0"]`, `,"library_ids":["0"]`,
		`,"library_ids":["3","-615"]`, `,"library_ids":["3","+615"]`, `,"library_ids":["3"," 615"]`, `,"library_ids":["3","615 "]`,
		`,"library_ids":["3","6.15"]`, `,"library_ids":["3","6e2"]`, `,"library_ids":["3","0x26"]`, `,"library_ids":["3",""]`,
		`,"library_ids":["3","*"]`, `,"library_ids":["3","٣"]`, `,"library_ids":["3","12345678901"]`,
		`,"library_ids":["3","c423189f0ca04f568a152eaeebd60d89"]`, `,"library_ids":["3","Anime"]`,
		`,"Library_ids":["3","615"]`, `,"library_IDs":["3","615"]`, `,"libraryids":["3","615"]`, `,"libraries":["3","615"]`,
		`,"library_ids":["3"],"library_ids":["3","615"]`, `,"library_ids":["3","615"],"library_ids":["3"]`,
		`,"library_ids":["3","615"],"extra":true`,
	} {
		if _, err := parseHolonetWriterPolicy([]byte(libraryPolicyJSON(tail))); err == nil {
			t.Fatal("invalid library policy accepted", tail)
		}
	}
	// The new field keeps the unchanged 8192-byte custody bound sufficient.
	if len(libraryPolicyJSON(`,"history_users":["`+strings.Repeat("b", 32)+`"],"library_ids":["3","615","1132"]`)) > 8192 {
		t.Fatal("maximal opt-in no longer fits the custody bound")
	}
}

func TestHolonetWriterSignedLibrariesMustEqualPolicyLibraries(t *testing.T) {
	key, keys, reader := holonetFixture(t)
	contract := holonetRecommendationContract(libraryPolicy(t, `,"library_ids":["3","615","1132"]`))
	old := holonetRecommendationContract(writerPolicy(t))
	check := func(claims map[string]any, contract holonetContract) error {
		return validateHolonetFor(signed(t, key, claims), keys, 2000000000, 2000000000, 300, contract)
	}
	valid := libraryClaims(reader, contract)
	if check(valid, contract) != nil {
		t.Fatal("exact library writer refused")
	}
	for _, order := range [][]string{seriesLibraries, {"615", "1132", "3"}, {"1132", "3", "615"}} {
		valid["holonet_libraries"] = order
		if check(valid, contract) != nil {
			t.Fatal("library permutation refused", order)
		}
	}
	oldValid := libraryClaims(reader, old)
	if !reflect.DeepEqual(oldValid["holonet_libraries"], []string{"3"}) || check(oldValid, old) != nil ||
		check(valid, old) == nil || check(oldValid, contract) == nil {
		t.Fatal("old and library writer contracts crossed")
	}
	// Ordinary readers stay exact Movies 3 with empty history.
	if validateHolonet(signed(t, key, valid), keys, 2000000000, 2000000000, 300) == nil {
		t.Fatal("reader admitted the writer library token")
	}
	readerWide := map[string]any{}
	for k, v := range reader {
		readerWide[k] = v
	}
	readerWide["holonet_libraries"] = seriesLibraries
	if validateHolonet(signed(t, key, readerWide), keys, 2000000000, 2000000000, 300) == nil ||
		validateHolonet(signed(t, key, reader), keys, 2000000000, 2000000000, 300) != nil {
		t.Fatal("reader library contract changed")
	}
	for _, value := range []any{
		[]string{"3"}, []string{"3", "615"}, []string{"615", "1132"}, []string{"3", "615", "1132", "4"},
		[]string{"3", "615", "4"}, []string{"3", "615", "1132", "3"}, []string{"3", "3", "615"},
		[]string{"03", "615", "1132"}, []string{"3", "0615", "1132"}, []string{"3", "615", "0"},
		[]string{"3", "615", "*"}, []string{"3", "615", " 1132"}, []int{3, 615, 1132}, []any{"3", 615, "1132"},
		[]string{}, nil, "3", "3 615 1132", map[string]bool{"3": true, "615": true, "1132": true},
	} {
		claims := map[string]any{}
		for k, v := range valid {
			claims[k] = v
		}
		claims["holonet_libraries"] = value
		if check(claims, contract) == nil {
			t.Fatalf("library mismatch accepted: %v", value)
		}
	}
	missing := map[string]any{}
	for k, v := range valid {
		missing[k] = v
	}
	delete(missing, "holonet_libraries")
	if check(missing, contract) == nil {
		t.Fatal("missing libraries accepted")
	}
	// The library opt-in widens neither actions, history nor the subject cohort.
	for _, tc := range []struct {
		field string
		value any
	}{
		{"holonet_actions", append(append([]string{}, holonetWriterActions...), holonetHistoryAction)},
		{"holonet_history_users", []string{strings.Repeat("b", 32)}}, {"holonet_target_users", []string{strings.Repeat("b", 32)}},
		{"holonet_catalog_users", []string{strings.Repeat("c", 32)}}, {"holonet_namespace", "movies-catalog"},
		{"scope", holonetWriterScope + " holonet.series"},
	} {
		claims := map[string]any{}
		for k, v := range valid {
			claims[k] = v
		}
		claims[tc.field] = tc.value
		if check(claims, contract) == nil {
			t.Fatalf("library writer widened: %s", tc.field)
		}
	}
	// History and libraries compose; each still must match its own policy set.
	b := strings.Repeat("b", 32)
	combined := holonetRecommendationContract(libraryPolicy(t, `,"history_users":["`+b+`"],"library_ids":["3","615","1132"]`))
	historyOnly := holonetRecommendationContract(historyPolicy(t, `["`+b+`"]`))
	combinedClaims := libraryClaims(reader, combined)
	if check(combinedClaims, combined) != nil || check(combinedClaims, historyOnly) == nil ||
		check(libraryClaims(reader, historyOnly), combined) == nil || check(valid, combined) == nil {
		t.Fatal("history and library sets crossed")
	}
}

func TestHolonetWriterLibraryExchangeKeepsFixedRequest(t *testing.T) {
	key, keys, reader := holonetFixture(t)
	contract := holonetRecommendationContract(libraryPolicy(t, `,"library_ids":["3","615","1132"]`))
	token := signed(t, key, libraryClaims(reader, contract))
	calls := 0
	client := httpClient()
	client.Transport = roundTrip(func(req *http.Request) (*http.Response, error) {
		calls++
		body := string(keys)
		switch req.URL.String() {
		case tokenURL:
			// Libraries add no form field, scope, user, resource or library selector.
			if req.Method != "POST" || req.ParseForm() != nil || len(req.PostForm) != 6 ||
				req.PostForm.Get("grant_type") != "client_credentials" || req.PostForm.Get("username") != holonetWriterUsername ||
				req.PostForm.Get("password") != "synthetic-writer-password" || req.PostForm.Get("scope") != holonetWriterScope ||
				req.PostForm.Get("resource") != holonetResource || req.PostForm.Get("client_id") != holonetClientID {
				t.Fatal("library writer exchange escaped fixed tuple")
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
		t.Fatal("library writer exchange failed")
	}
	if got, err := acquireHolonetFor(context.Background(), client, "synthetic-writer-password", now,
		holonetRecommendationContract(writerPolicy(t))); err == nil || got != "" || calls != 4 {
		t.Fatal("old writer admitted a library token")
	}
}
