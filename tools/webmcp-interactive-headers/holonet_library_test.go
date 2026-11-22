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

func holonetLibraryClaims(original map[string]any) map[string]any {
	c := make(map[string]any, len(original))
	for k, v := range original {
		c[k] = v
	}
	contract := holonetLibraryContract()
	c["scope"] = contract.scope
	c["holonet_namespace"] = contract.namespace
	c["holonet_libraries"] = []string{"3", "615", "1132"}
	c["holonet_actions"] = contract.actions
	c["holonet_catalog_users"] = []string{}
	c["holonet_history_users"] = []string{}
	c["holonet_target_users"] = []string{}
	return c
}

func TestHolonetLibrarySignedAndDisjoint(t *testing.T) {
	key, keys, reader := holonetFixture(t)
	contract := holonetLibraryContract()
	claims := holonetLibraryClaims(reader)
	check := func(c map[string]any) error {
		return validateHolonetFor(signed(t, key, c), keys, 2000000000, 2000000000, 300, contract)
	}
	if check(claims) != nil {
		t.Fatal("exact library claims refused")
	}
	// Any permutation of the exact three libraries is accepted.
	permuted := holonetLibraryClaims(reader)
	permuted["holonet_libraries"] = []string{"1132", "615", "3"}
	if check(permuted) != nil {
		t.Fatal("permuted exact library set refused")
	}
	if check(reader) == nil || check(seedJoinClaims(reader)) == nil || check(torrentClaims(reader)) == nil ||
		check(acquirePurposeClaims(reader, "read")) == nil {
		t.Fatal("old token admitted")
	}
	for field, value := range map[string]any{
		"scope":                 "holonet.library holonet.read",
		"holonet_namespace":     "managed-janitor",
		"holonet_libraries":     []string{"3", "615"},
		"holonet_actions":       []string{"library.read"},
		"holonet_catalog_users": []string{holonetUser},
		"holonet_history_users": []string{holonetUser},
		"holonet_target_users":  []string{holonetUser},
		"holonet_library":       map[string]any{"libraries": []string{"3", "615", "1132"}},
		"iss":                   ovIssuer,
		"aud":                   resource,
		"azp":                   "foreign",
		"exp":                   1999999999,
	} {
		c := holonetLibraryClaims(reader)
		c[field] = value
		if check(c) == nil {
			t.Fatal("drift admitted", field)
		}
	}
	for _, bad := range [][]string{
		{"3"},
		{"3", "3", "615"},
		{"3", "615", "1132", "999"},
	} {
		c := holonetLibraryClaims(reader)
		c["holonet_libraries"] = bad
		if check(c) == nil {
			t.Fatal("bad library set admitted", bad)
		}
	}
	for _, bad := range [][]string{
		{"library.manage", "library.read"},
		{"library.read", "library.manage", "object.delete"},
	} {
		c := holonetLibraryClaims(reader)
		c["holonet_actions"] = bad
		if check(c) == nil {
			t.Fatal("bad actions admitted", bad)
		}
	}
	for _, host := range []string{"laptop", "omarchy-pc"} {
		if selectMode([]string{"holonet-library", host}) != "holonet-library" {
			t.Fatal("closed mode refused", host)
		}
	}
	for _, args := range [][]string{
		{"holonet-library"},
		{"holonet-library", "agent-a"},
		{"holonet-library", "agent-b"},
		{"holonet-library", "gaming-pc"},
		{"holonet-library", "laptop", "--scope=x"},
		{"holonet-library", "omarchy-pc", "extra"},
	} {
		if selectMode(args) != "" {
			t.Fatal("open mode admitted", args)
		}
	}
	if ovFullBinding("laptop", "omarchy-macbook-air-igor", 1001) != nil ||
		ovFullBinding("omarchy-pc", "omarchy-pc", 1000) != nil {
		t.Fatal("approved host binding refused")
	}
	for _, bad := range []struct {
		host, node string
		uid        int
	}{
		{"laptop", "omarchy-pc", 1001},
		{"laptop", "omarchy-macbook-air-igor", 1000},
		{"omarchy-pc", "omarchy-macbook-air-igor", 1000},
		{"omarchy-pc", "omarchy-pc", 1001},
		{"agent-a", "agent-a", 1000},
	} {
		if ovFullBinding(bad.host, bad.node, bad.uid) == nil {
			t.Fatal("wrong host binding admitted", bad)
		}
	}
}

func TestHolonetLibraryUsesOriginalWriterAndExactExchange(t *testing.T) {
	defer func() { hostIdentityUsername = "" }()
	key, keys, reader := holonetFixture(t)
	contract := holonetLibraryContract()
	token := signed(t, key, holonetLibraryClaims(reader))

	for _, hostIdentity := range []string{"", "chaldea-laptop", "chaldea-omarchy-pc"} {
		hostIdentityUsername = hostIdentity
		path, err := holonetCredentialPathFor(os.Getuid(), contract)
		if err != nil || !strings.HasSuffix(path, "/"+holonetWriterCredential) {
			t.Fatal("library credential moved to host identity", hostIdentity, path)
		}
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
				want := map[string]string{
					"grant_type": "client_credentials",
					"client_id":  holonetClientID,
					"username":   holonetWriterUsername,
					"password":   "synthetic-password",
					"scope":      holonetLibraryScope,
					"resource":   holonetResource,
				}
				if len(r.Form) != len(want) {
					t.Fatal("extra form")
				}
				for k, v := range want {
					if len(r.Form[k]) != 1 || r.Form.Get(k) != v {
						t.Fatal("form", k)
					}
				}
				raw, _ := json.Marshal(map[string]any{
					"access_token": token,
					"token_type":   "Bearer",
					"expires_in":   300,
					"scope":        holonetLibraryScope,
				})
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
			t.Fatal("fixed library acquisition", hostIdentity, err, calls)
		}
	}
}

func TestHolonetLibraryCredentialNeverFallsBack(t *testing.T) {
	home := t.TempDir()
	if err := os.Chmod(home, 0700); err != nil {
		t.Fatal(err)
	}
	dir := filepath.Join(home, ".config/chaldea/authentik")
	if err := os.MkdirAll(dir, 0700); err != nil {
		t.Fatal(err)
	}
	// Even when host.app-password exists, missing writer credential must fail.
	hostPath := filepath.Join(home, hostCredential)
	if err := os.WriteFile(hostPath, []byte("FixtureHostPassword0123456789"), 0600); err != nil {
		t.Fatal(err)
	}
	writerPath := filepath.Join(home, holonetWriterCredential)
	if _, err := readOVCredential(writerPath, os.Getuid()); err == nil {
		t.Fatal("missing writer credential admitted")
	}
	if err := os.WriteFile(writerPath, []byte("FixtureLibraryWriterPass0123456"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(writerPath, 0644); err != nil {
		t.Fatal(err)
	}
	if _, err := readOVCredential(writerPath, os.Getuid()); err == nil {
		t.Fatal("world-readable writer credential admitted")
	}
	if err := os.Chmod(writerPath, 0600); err != nil {
		t.Fatal(err)
	}
	got, err := readOVCredential(writerPath, os.Getuid())
	if err != nil || got != "FixtureLibraryWriterPass0123456" {
		t.Fatal("protected writer credential refused", err)
	}
}
