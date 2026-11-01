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
var holonetWriterActions = []string{"catalog.read", "playlist.read", "playlist.manage", "object.share", "home.read", "home.manage", "object.delete"}

// The issuer appends this one action after the exact writer tuple when the
// public policy opts recipients into scoped playback history.
const holonetHistoryAction = "history.read"

type holonetContract struct {
	username, scope, namespace string
	targets, history, actions  []string
	writer                     bool
}
type holonetWriterPolicy struct {
	Version int      `json:"version"`
	Owner   string   `json:"owner"`
	Targets []string `json:"target_users"`
	History []string `json:"history_users,omitempty"`
}

func holonetReaderContract() holonetContract {
	return holonetContract{username: holonetUsername, scope: holonetScope, namespace: "movies-catalog",
		targets: []string{}, history: []string{}, actions: []string{"catalog.read"}}
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
	return holonetContract{username: holonetWriterUsername, scope: holonetWriterScope,
		namespace: "managed-recommendations", targets: targets, history: history, actions: actions, writer: true}
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
	// history_users is the only optional field; null never stands for empty.
	history, hasHistory := shape["history_users"]
	if len(shape) != 3 && !(hasHistory && len(shape) == 4) || hasHistory && (len(history) == 0 || history[0] != '[') {
		return holonetWriterPolicy{}, denied
	}
	var policy holonetWriterPolicy
	if strictJSON(data, &policy) != nil || policy.Version != 1 || policy.Owner != holonetWriterPolicyOwner ||
		len(policy.Targets) < 1 || len(policy.Targets) > 16 {
		return holonetWriterPolicy{}, denied
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
