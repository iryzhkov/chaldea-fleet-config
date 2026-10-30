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

type holonetContract struct {
	username, scope, namespace string
	targets, actions           []string
	writer                     bool
}
type holonetWriterPolicy struct {
	Version int      `json:"version"`
	Owner   string   `json:"owner"`
	Targets []string `json:"target_users"`
}

func holonetReaderContract() holonetContract {
	return holonetContract{username: holonetUsername, scope: holonetScope, namespace: "movies-catalog",
		targets: []string{}, actions: []string{"catalog.read"}}
}
func holonetRecommendationContract(policy holonetWriterPolicy) holonetContract {
	targets := append([]string{}, policy.Targets...)
	sort.Strings(targets)
	return holonetContract{username: holonetWriterUsername, scope: holonetWriterScope,
		namespace: "managed-recommendations", targets: targets, actions: holonetWriterActions, writer: true}
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
func (c holonetContract) exactTargets(claims map[string]json.RawMessage) bool {
	if !c.writer {
		return exactHolonetList(claims, "holonet_target_users", c.targets)
	}
	raw, ok := claims["holonet_target_users"]
	if !ok || len(raw) == 0 || raw[0] != '[' {
		return false
	}
	var actual []string
	if json.Unmarshal(raw, &actual) != nil || len(actual) != len(c.targets) {
		return false
	}
	sort.Strings(actual)
	for i, value := range actual {
		if value != c.targets[i] {
			return false
		}
	}
	return true
}
func parseHolonetWriterPolicy(data []byte) (holonetWriterPolicy, error) {
	var shape map[string]json.RawMessage
	if strictJSON(data, &shape) != nil || len(shape) != 3 || shape["version"] == nil || shape["owner"] == nil || shape["target_users"] == nil {
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
	sort.Strings(policy.Targets)
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
