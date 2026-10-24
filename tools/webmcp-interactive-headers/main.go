// webmcp-interactive-headers is a closed, uncached native headers helper.
// Trust: system HTTPS roots at fixed issuer/JWKS endpoints, then RS256 verification.
// No CLI/config option can select another endpoint, resource, scope or client.
package main

import (
	"bytes"
	"context"
	"crypto"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math/big"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/user"
	"path/filepath"
	"strings"
	"syscall"
	"time"
)

const origin = "https://auth.ryzhkov.dev"
const clientID = "jocasta-managed-interactive"
const issuer = origin + "/application/o/" + clientID + "/"
const resource = "https://jocasta.mcp.ryzhkov.dev/mcp"
const scopes = "jocasta.read jocasta.write"
const tokenURL = origin + "/application/o/token/"
const jwksURL = issuer + "jwks/"

var denied = errors.New("managed headers unavailable")
var hosts = map[string]bool{"laptop": true, "agent-a": true, "agent-b": true, "omarchy-pc": true}

type enrollment struct {
	Version    int    `json:"version"`
	Host       string `json:"host"`
	Username   string `json:"username"`
	Password   string `json:"password"`
	Generation int    `json:"generation"`
	Owner      string `json:"owner"`
}

func main() {
	if len(os.Args) != 3 || os.Args[1] != "jocasta" || !hosts[os.Args[2]] {
		fail()
	}
	current, err := user.Current()
	if err != nil {
		fail()
	}
	entry, err := readEnrollment(filepath.Join(current.HomeDir, ".config/webmcp-interactive/enrollment.json"), os.Getuid(), os.Args[2])
	if err != nil {
		fail()
	}
	ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
	defer cancel()
	token, err := acquire(ctx, httpClient(), entry, time.Now)
	if err != nil {
		fail()
	}
	// This pipe is the only token output; no file or persistent token cache.
	if json.NewEncoder(os.Stdout).Encode(map[string]string{"Authorization": "Bearer " + token}) != nil {
		os.Exit(1)
	}
}

func fail() {
	fmt.Fprintln(os.Stderr, denied.Error())
	os.Exit(1)
}

// Hold each directory FD through openat. No ancestor or leaf symlink is followed.
// Root/this UID may own ancestors; only this UID may own the private leaf.
func readEnrollment(path string, uid int, host string) (enrollment, error) {
	var out enrollment
	if !hosts[host] || !filepath.IsAbs(path) || filepath.Clean(path) != path {
		return out, denied
	}
	fd, err := syscall.Open("/", syscall.O_RDONLY|syscall.O_DIRECTORY|syscall.O_CLOEXEC, 0)
	if err != nil {
		return out, denied
	}
	defer func() { syscall.Close(fd) }()
	parts := strings.Split(strings.TrimPrefix(path, "/"), "/")
	for _, part := range parts[:len(parts)-1] {
		var st syscall.Stat_t
		if syscall.Fstat(fd, &st) != nil || st.Mode&0022 != 0 || (st.Uid != 0 && int(st.Uid) != uid) {
			return out, denied
		}
		next, e := syscall.Openat(fd, part, syscall.O_RDONLY|syscall.O_DIRECTORY|syscall.O_NOFOLLOW|syscall.O_CLOEXEC, 0)
		if e != nil {
			return out, denied
		}
		syscall.Close(fd)
		fd = next
	}
	var parent syscall.Stat_t
	if syscall.Fstat(fd, &parent) != nil || int(parent.Uid) != uid || parent.Mode&0077 != 0 {
		return out, denied
	}
	leaf, err := syscall.Openat(fd, parts[len(parts)-1], syscall.O_RDONLY|syscall.O_NOFOLLOW|syscall.O_NONBLOCK|syscall.O_CLOEXEC, 0)
	if err != nil {
		return out, denied
	}
	file := os.NewFile(uintptr(leaf), "enrollment")
	defer file.Close()
	info, err := file.Stat()
	if err != nil {
		return out, denied
	}
	st, ok := info.Sys().(*syscall.Stat_t)
	if !ok || !info.Mode().IsRegular() || info.Mode().Perm() != 0600 || int(st.Uid) != uid || st.Nlink != 1 || info.Size() < 1 || info.Size() > 4096 {
		return out, denied
	}
	data, err := io.ReadAll(io.LimitReader(file, 4097))
	if err != nil || len(data) > 4096 || strictJSON(data, &out) != nil {
		return out, denied
	}
	after, e := file.Stat()
	if e != nil || after.Size() != info.Size() || !after.ModTime().Equal(info.ModTime()) {
		return out, denied
	}
	if out.Version != 1 || out.Host != host || out.Username != "webmcp-interactive-"+host || out.Generation < 1 || out.Generation > 1000 || len(out.Owner) != 36 || len(out.Password) < 16 || len(out.Password) > 256 {
		return enrollment{}, denied
	}
	for _, b := range []byte(out.Password) {
		if b < 33 || b > 126 {
			return enrollment{}, denied
		}
	}
	return out, nil
}

// Reject duplicate JSON names, including in nested objects. Go's ordinary decoder
// would otherwise silently select the last occurrence of a security claim.
func strictJSON(data []byte, out any) error {
	dec := json.NewDecoder(bytes.NewReader(data))
	var value func() error
	value = func() error {
		t, e := dec.Token()
		if e != nil {
			return denied
		}
		if delim, ok := t.(json.Delim); ok {
			switch delim {
			case '{':
				seen := map[string]bool{}
				for dec.More() {
					key, e := dec.Token()
					if e != nil {
						return denied
					}
					name, ok := key.(string)
					if !ok || seen[name] {
						return denied
					}
					seen[name] = true
					if value() != nil {
						return denied
					}
				}
				end, e := dec.Token()
				if e != nil || end != json.Delim('}') {
					return denied
				}
			case '[':
				for dec.More() {
					if value() != nil {
						return denied
					}
				}
				end, e := dec.Token()
				if e != nil || end != json.Delim(']') {
					return denied
				}
			default:
				return denied
			}
		}
		return nil
	}
	if value() != nil {
		return denied
	}
	if _, e := dec.Token(); e != io.EOF {
		return denied
	}
	return json.Unmarshal(data, out)
}

func httpClient() *http.Client {
	return &http.Client{
		Timeout: 8 * time.Second,
		Transport: &http.Transport{Proxy: nil, DialContext: (&net.Dialer{Timeout: 3 * time.Second}).DialContext,
			TLSHandshakeTimeout: 3 * time.Second, ResponseHeaderTimeout: 4 * time.Second, MaxResponseHeaderBytes: 8192,
			DisableKeepAlives: true},
		CheckRedirect: func(*http.Request, []*http.Request) error { return denied },
	}
}

func response(ctx context.Context, client *http.Client, method, endpoint string, body io.Reader, limit int64) ([]byte, error) {
	req, err := http.NewRequestWithContext(ctx, method, endpoint, body)
	if err != nil {
		return nil, denied
	}
	req.Header.Set("Accept", "application/json")
	if method == "POST" {
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	}
	res, err := client.Do(req)
	if err != nil {
		return nil, denied
	}
	defer res.Body.Close()
	// Never read or report an error response, redirect target, or credential echo.
	if res.StatusCode != 200 {
		return nil, denied
	}
	data, err := io.ReadAll(io.LimitReader(res.Body, limit+1))
	if err != nil || int64(len(data)) > limit {
		return nil, denied
	}
	return data, nil
}

func acquire(ctx context.Context, client *http.Client, entry enrollment, now func() time.Time) (string, error) {
	form := url.Values{"grant_type": {"client_credentials"}, "client_id": {clientID}, "username": {entry.Username},
		"password": {entry.Password}, "scope": {scopes}, "resource": {resource}}
	start := now().Unix()
	data, err := response(ctx, client, "POST", tokenURL, strings.NewReader(form.Encode()), 32768)
	if err != nil {
		return "", denied
	}
	var result struct {
		AccessToken string          `json:"access_token"`
		TokenType   string          `json:"token_type"`
		ExpiresIn   int64           `json:"expires_in"`
		Scope       string          `json:"scope"`
		Refresh     json.RawMessage `json:"refresh_token"`
	}
	if strictJSON(data, &result) != nil || !strings.EqualFold(result.TokenType, "Bearer") || result.ExpiresIn <= 30 || result.ExpiresIn > 300 || !exactScopes(result.Scope) || len(result.Refresh) != 0 {
		return "", denied
	}
	keys, err := response(ctx, client, "GET", jwksURL, nil, 65536)
	if err != nil {
		return "", denied
	}
	if validateToken(result.AccessToken, keys, entry.Username, now().Unix(), start, result.ExpiresIn) != nil {
		return "", denied
	}
	return result.AccessToken, nil
}

func exactScopes(s string) bool {
	f := strings.Fields(s)
	return len(f) == 2 && ((f[0] == "jocasta.read" && f[1] == "jocasta.write") || (f[1] == "jocasta.read" && f[0] == "jocasta.write"))
}

func validateToken(token string, keys []byte, identity string, now, start, expires int64) error {
	if len(token) < 1 || len(token) > 16384 {
		return denied
	}
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return denied
	}
	decode := base64.RawURLEncoding.Strict().DecodeString
	header, err := decode(parts[0])
	if err != nil {
		return denied
	}
	claims, err := decode(parts[1])
	if err != nil {
		return denied
	}
	sig, err := decode(parts[2])
	if err != nil {
		return denied
	}
	var h struct {
		Alg  string
		Kid  string
		Crit json.RawMessage
		JKU  json.RawMessage
		X5U  json.RawMessage
		B64  json.RawMessage
	}
	if strictJSON(header, &h) != nil || h.Alg != "RS256" || len(h.Kid) == 0 || len(h.Kid) > 256 || len(h.Crit) > 0 || len(h.JKU) > 0 || len(h.X5U) > 0 || len(h.B64) > 0 {
		return denied
	}
	var set struct {
		Keys []struct{ Kty, Use, Alg, Kid, N, E string }
	}
	if strictJSON(keys, &set) != nil || len(set.Keys) < 1 || len(set.Keys) > 16 {
		return denied
	}
	var key *rsa.PublicKey
	for _, j := range set.Keys {
		if j.Kid != h.Kid {
			continue
		}
		if key != nil || j.Kty != "RSA" || j.Use != "sig" || j.Alg != "RS256" {
			return denied
		}
		n, e := decode(j.N)
		if e != nil || len(n) < 256 || len(n) > 1024 {
			return denied
		}
		exponent, e := decode(j.E)
		if e != nil || len(exponent) < 1 || len(exponent) > 4 {
			return denied
		}
		ev := new(big.Int).SetBytes(exponent).Int64()
		if ev < 3 || ev > 2147483647 || ev%2 == 0 {
			return denied
		}
		key = &rsa.PublicKey{N: new(big.Int).SetBytes(n), E: int(ev)}
	}
	if key == nil {
		return denied
	}
	hash := sha256.Sum256([]byte(parts[0] + "." + parts[1]))
	if rsa.VerifyPKCS1v15(key, crypto.SHA256, hash[:], sig) != nil {
		return denied
	}
	// These checks follow signature verification. Decoding alone assures nothing.
	var c struct {
		Iss, Sub, Azp, Scope string
		Aud                  json.RawMessage
		Iat, Exp             int64
		Nbf                  *int64
		Operator             bool            `json:"jocasta_operator"`
		Identity             string          `json:"webmcp_identity"`
		Projects             json.RawMessage `json:"jocasta_projects"`
	}
	if strictJSON(claims, &c) != nil {
		return denied
	}
	var aud string
	if json.Unmarshal(c.Aud, &aud) != nil {
		var list []string
		if json.Unmarshal(c.Aud, &list) != nil || len(list) != 1 {
			return denied
		}
		aud = list[0]
	}
	if c.Iss != issuer || aud != resource || c.Azp != clientID || !exactScopes(c.Scope) || !c.Operator || c.Identity != identity || len(c.Projects) > 0 || len(c.Sub) < 1 || len(c.Sub) > 256 {
		return denied
	}
	if c.Iat <= 0 || c.Iat > now+5 || c.Exp-c.Iat <= 0 || c.Exp-c.Iat > 300 || c.Exp-now <= 30 || c.Exp-now > 300 || c.Iat < start-5 || c.Exp > start+expires+5 || (c.Nbf != nil && *c.Nbf > now) {
		return denied
	}
	return nil
}
