package main

import (
	"os"
	"path/filepath"
)

// A root-owned selector changes custody only. Native adapters, resource requests,
// signature checks and purpose contracts remain independent and unchanged.
const hostCredential = ".config/chaldea/authentik/host.app-password"
const hostIdentityDirectory = "/etc/webmcp-interactive"

var hostIdentityUsername string

func identityUsername(legacy string) string {
	if hostIdentityUsername != "" {
		return hostIdentityUsername
	}
	return legacy
}

func hostIdentitySelected(path, host string) (bool, error) {
	if _, err := os.Lstat(path); os.IsNotExist(err) {
		return false, nil
	}
	data, err := readOwned(path, 0, 0644, false, 128)
	if err != nil || string(data) != "chaldea-fleet-config host identity v1 "+host+"\n" {
		return false, denied
	}
	return true, nil
}

func configureHostIdentity(host string) error {
	enabled, err := hostIdentitySelected(filepath.Join(hostIdentityDirectory, "host-identity-"+host), host)
	if err != nil || !enabled {
		return err
	}
	node, err := os.Hostname()
	expectedNode := host
	expectedUID := 1000
	if host == "laptop" {
		expectedNode = "omarchy-macbook-air-igor"
		expectedUID = 1001
	}
	if err != nil || !hosts[host] || node != expectedNode || os.Getuid() != expectedUID {
		return denied
	}
	hostIdentityUsername = "chaldea-" + host
	path, err := credentialPath(os.Getuid(), hostCredential)
	if err != nil {
		return denied
	}
	// Validate before any network request. Never fall back after selection.
	_, err = readOVCredential(path, os.Getuid())
	return err
}

func interactiveEnrollment(home string, uid int, host string) (enrollment, error) {
	if hostIdentityUsername == "" {
		return readEnrollment(filepath.Join(home, ".config/webmcp-interactive/enrollment.json"), uid, host)
	}
	password, err := readOVCredential(filepath.Join(home, hostCredential), uid)
	if err != nil {
		return enrollment{}, err
	}
	return enrollment{Host: host, Username: hostIdentityUsername, Password: password}, nil
}
