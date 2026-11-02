package main

import (
	"context"
	"encoding/json"
	"os"
	"regexp"
	"sort"
	"strings"
	"time"
)

const holonetWriterScope = "holonet.read holonet.curate holonet.home"
const holonetWriterUsername = "chaldea-laptop-holonet-recommendations"
const holonetWriterCredential = ".config/chaldea/authentik/holonet-recommendations.app-password"
const holonetWriterPolicyPath = "/etc/webmcp-interactive/holonet-recommendations.json"
const holonetWriterPolicyOwner = "chaldea-fleet-config holonet recommendations"

var holonetTargetID = regexp.MustCompile("^[0-9a-f]{32}$")

// Canonical decimal library IDs: no sign, no leading zero, no zero.
var holonetLibraryID = regexp.MustCompile("^[1-9][0-9]{0,9}$")

// The Movies library every reader and writer has always carried.
const holonetDefaultLibrary = "3"

var holonetWriterActions = []string{"catalog.read", "playlist.read", "playlist.manage", "object.share", "home.read", "home.manage", "object.delete"}

// The issuer appends this one action after the exact writer tuple when the
// public policy opts recipients into scoped playback history.
const holonetHistoryAction = "history.read"

type holonetContract struct {
	username, scope, namespace           string
	targets, history, actions, libraries []string
	writer                               bool
}
type holonetWriterPolicy struct {
	Version   int      `json:"version"`
	Owner     string   `json:"owner"`
	Targets   []string `json:"target_users"`
	History   []string `json:"history_users,omitempty"`
	Libraries []string `json:"library_ids,omitempty"`
}

func holonetReaderContract() holonetContract {
	return holonetContract{username: holonetUsername, scope: holonetScope, namespace: "movies-catalog",
		targets: []string{}, history: []string{}, actions: []string{"catalog.read"},
		libraries: []string{holonetDefaultLibrary}}
}

// History authority comes only from the policy's explicit history_users, never
// from the target cohort. An absent or empty set keeps the original contract.
func holonetRecommendationContract(policy holonetWriterPolicy) holonetContract {
	targets := append([]string{}, policy.Targets...)
	sort.Strings(targets)
	history := append([]string{}, policy.History...)
	sort.Strings(history)
	actions := append([]string{}, holonetWriterActions...)
	if len(history) > 0 {
		actions = append(actions, holonetHistoryAction)
	}
	// An absent library_ids keeps the original Movies-only writer; the parser
	// never lets a supplied empty set reach this point.
	libraries := []string{holonetDefaultLibrary}
	if len(policy.Libraries) > 0 {
		libraries = append([]string{}, policy.Libraries...)
		sort.Strings(libraries)
	}
	return holonetContract{username: holonetWriterUsername, scope: holonetWriterScope,
		namespace: "managed-recommendations", targets: targets, history: history, actions: actions,
		libraries: libraries, writer: true}
}
func (c holonetContract) acceptScope(value string) bool {
	if !c.writer {
		return value == c.scope
	}
	fields := strings.Fields(value)
	if len(fields) != 3 || strings.Join(fields, " ") != value {
		return false
	}
	sort.Strings(fields)
	return strings.Join(fields, " ") == "holonet.curate holonet.home holonet.read"
}

// A writer's signed recipient sets must equal the policy sets in any order;
// want is sorted and unique, so a duplicate, foreign or missing ID refuses.
func (c holonetContract) exactSet(claims map[string]json.RawMessage, key string, want []string) bool {
	if !c.writer {
		return exactHolonetList(claims, key, want)
	}
	raw, ok := claims[key]
	if !ok || len(raw) == 0 || raw[0] != '[' {
		return false
	}
	var actual []string
	if json.Unmarshal(raw, &actual) != nil || len(actual) != len(want) {
		return false
	}
	sort.Strings(actual)
	for i, value := range actual {
		if value != want[i] {
			return false
		}
	}
	return true
}
func parseHolonetWriterPolicy(data []byte) (holonetWriterPolicy, error) {
	var shape map[string]json.RawMessage
	if strictJSON(data, &shape) != nil || shape["version"] == nil || shape["owner"] == nil || shape["target_users"] == nil {
		return holonetWriterPolicy{}, denied
	}
	// history_users and library_ids are the only optional fields; exact names
	// only (Go's decoder would fold case aliases), and null never stands for empty.
	for name, raw := range shape {
		switch name {
		case "version", "owner", "target_users":
		case "history_users", "library_ids":
			if len(raw) == 0 || raw[0] != '[' {
				return holonetWriterPolicy{}, denied
			}
		default:
			return holonetWriterPolicy{}, denied
		}
	}
	var policy holonetWriterPolicy
	if strictJSON(data, &policy) != nil || policy.Version != 1 || policy.Owner != holonetWriterPolicyOwner ||
		len(policy.Targets) < 1 || len(policy.Targets) > 16 {
		return holonetWriterPolicy{}, denied
	}
	// A supplied set is explicit: never empty, at most three, and always
	// including the Movies library so the original writer scope stays within it.
	if _, hasLibraries := shape["library_ids"]; hasLibraries {
		if len(policy.Libraries) < 1 || len(policy.Libraries) > 3 {
			return holonetWriterPolicy{}, denied
		}
		libraries, movies := map[string]bool{}, false
		for _, id := range policy.Libraries {
			if !holonetLibraryID.MatchString(id) || libraries[id] {
				return holonetWriterPolicy{}, denied
			}
			libraries[id] = true
			movies = movies || id == holonetDefaultLibrary
		}
		if !movies {
			return holonetWriterPolicy{}, denied
		}
	}
	seen := map[string]bool{}
	for _, id := range policy.Targets {
		if !holonetTargetID.MatchString(id) || seen[id] {
			return holonetWriterPolicy{}, denied
		}
		seen[id] = true
	}
	recipients := map[string]bool{}
	for _, id := range policy.History {
		if !seen[id] || recipients[id] {
			return holonetWriterPolicy{}, denied
		}
		recipients[id] = true
	}
	sort.Strings(policy.Targets)
	sort.Strings(policy.History)
	sort.Strings(policy.Libraries)
	return policy, nil
}
func readHolonetWriterPolicy(path string) (holonetWriterPolicy, error) {
	// Public data, with root-only modification and no-follow FD custody. The
	// caller can select neither another path nor another policy through CLI.
	data, err := readOwned(path, 0, 0644, false, 8192)
	if err != nil {
		return holonetWriterPolicy{}, denied
	}
	return parseHolonetWriterPolicy(data)
}
func holonetWriterMode() {
	node, err := os.Hostname()
	if err != nil || holonetBinding(node, os.Getuid()) != nil {
		fail()
	}
	policy, err := readHolonetWriterPolicy(holonetWriterPolicyPath)
	if err != nil {
		fail()
	}
	path, err := credentialPath(os.Getuid(), holonetWriterCredential)
	if err != nil {
		fail()
	}
	password, err := readOVCredential(path, os.Getuid())
	if err != nil {
		fail()
	}
	ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
	defer cancel()
	token, err := acquireHolonetFor(ctx, httpClient(), password, time.Now, holonetRecommendationContract(policy))
	if err != nil {
		fail()
	}
	emit(token)
}
