package main

import (
	"context"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestHostIdentityRequestsStaySeparate(t *testing.T) {
	defer func() { hostIdentityUsername = "" }()
	for _, host := range []string{"laptop", "omarchy-pc", "agent-a", "agent-b"} {
		hostIdentityUsername = "chaldea-" + host
		check := func(wantClient, scope, resource string, run func(*http.Client)) {
			t.Helper()
			calls := 0
			client := httpClient()
			client.Transport = roundTrip(func(req *http.Request) (*http.Response, error) {
				calls++
				if req.Method != "POST" || req.ParseForm() != nil {
					t.Fatal("unexpected request")
				}
				f := req.PostForm
				if f.Get("username") != hostIdentityUsername || f.Get("password") != "FixtureHostPassword0123456789" || f.Get("client_id") != wantClient || f.Get("scope") != scope || f.Get("resource") != resource {
					t.Fatal("credential or purpose crossed")
				}
				if len(f["scope"]) != 1 || len(f["resource"]) > 1 {
					t.Fatal("combined purposes")
				}
				return &http.Response{StatusCode: 403, Body: io.NopCloser(strings.NewReader(""))}, nil
			})
			run(client)
			if calls != 1 {
				t.Fatal("fallback or extra request")
			}
		}
		now := time.Now
		ctx := context.Background()
		password := "FixtureHostPassword0123456789"
		check(clientID, scopes, resource, func(c *http.Client) {
			acquire(ctx, c, enrollment{Username: hostIdentityUsername, Password: password}, now)
		})
		if host == "agent-a" || host == "agent-b" {
			continue
		}
		check(ovClientID, ovFullRequestScopes, "", func(c *http.Client) { acquireOVFull(ctx, c, host, password, now) })
		check(shizuneClientID, shizuneScope, "", func(c *http.Client) { acquireShizune(ctx, c, host, password, now) })
		if host != "laptop" {
			continue
		}
		check(ovClientID, ovScope, "", func(c *http.Client) { acquireOV(ctx, c, password, now) })
		for _, contract := range []holonetContract{holonetReaderContract(), holonetRecommendationContract(holonetWriterPolicy{Targets: []string{holonetUser}}), holonetJanitorContract(), holonetTorrentsContract(), holonetSeedJoinContract(), holonetAcquireContract("read"), holonetAcquireContract("start"), holonetAcquireContract("media")} {
			check(holonetClientID, contract.scope, holonetResource, func(c *http.Client) { acquireHolonetFor(ctx, c, password, now, contract) })
		}
	}
}

func TestHostCredentialNeverFallsBack(t *testing.T) {
	defer func() { hostIdentityUsername = "" }()
	home := t.TempDir()
	os.Chmod(home, 0700)
	hostIdentityUsername = "chaldea-agent-b"
	if _, err := interactiveEnrollment(home, os.Getuid(), "agent-b"); err == nil {
		t.Fatal("missing credential admitted")
	}
	dir := filepath.Join(home, ".config/chaldea/authentik")
	if err := os.MkdirAll(dir, 0700); err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(home, hostCredential)
	if err := os.WriteFile(path, []byte("FixtureHostPassword0123456789"), 0600); err != nil {
		t.Fatal(err)
	}
	entry, err := interactiveEnrollment(home, os.Getuid(), "agent-b")
	if err != nil || entry.Username != "chaldea-agent-b" {
		t.Fatal("host credential refused")
	}
	os.Chmod(path, 0644)
	if _, err := interactiveEnrollment(home, os.Getuid(), "agent-b"); err == nil {
		t.Fatal("unsafe credential admitted")
	}
	os.Remove(path)
	if _, err := interactiveEnrollment(home, os.Getuid(), "agent-b"); err == nil {
		t.Fatal("deleted credential fell back")
	}
}

func TestHostSignedIdentity(t *testing.T) {
	key, jwks, claims := fixture(t)
	claims["webmcp_identity"] = "chaldea-agent-b"
	token := signed(t, key, claims)
	if validateToken(token, jwks, "chaldea-agent-b", 2000000000, 2000000000, 300) != nil {
		t.Fatal("new identity refused")
	}
	for _, identity := range []string{"webmcp-interactive-agent-b", "chaldea-agent-a"} {
		if validateToken(token, jwks, identity, 2000000000, 2000000000, 300) == nil {
			t.Fatal("wrong identity admitted")
		}
	}
}
