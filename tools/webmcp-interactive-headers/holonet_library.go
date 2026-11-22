package main

import (
	"context"
	"os"
	"time"
)

const holonetLibraryScope = "holonet.library"

// Closed library management contract on the M3 host identities (chaldea-laptop
// and chaldea-omarchy-pc). No caller supplies scopes, actions, resource,
// identity, libraries or credential. Both laptop and omarchy-pc authenticate
// through the host identity selector and host.app-password; never the original
// writer username or holonet-recommendations.app-password, and never falling back.
func holonetLibraryContract() holonetContract {
	return holonetContract{
		scope:     holonetLibraryScope,
		namespace: "managed-library",
		libraries: []string{"1132", "3", "615"},
		catalog:   []string{},
		targets:   []string{},
		history:   []string{},
		actions:   []string{"library.read", "library.manage"},
		writer:    true,
	}
}

func holonetLibraryCredentialPath(uid int, host string) (string, error) {
	if _, ok := ovFullHosts[host]; !ok || hostIdentityUsername != "chaldea-"+host {
		return "", denied
	}
	return ownCredentialPath(uid, hostCredential)
}

func holonetLibraryMode(host string) {
	node, err := os.Hostname()
	if err != nil || ovFullBinding(host, node, os.Getuid()) != nil {
		fail()
	}
	path, err := holonetLibraryCredentialPath(os.Getuid(), host)
	if err != nil {
		fail()
	}
	password, err := readOVCredential(path, os.Getuid())
	if err != nil {
		fail()
	}
	ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
	defer cancel()
	token, err := acquireHolonetFor(ctx, httpClient(), password, time.Now, holonetLibraryContract())
	if err != nil {
		fail()
	}
	emit(token)
}
