package main

import (
	"context"
	"os"
	"time"
)

const holonetLibraryScope = "holonet.library"

// Closed library management contract on the existing original writer account.
// No caller supplies scopes, actions, resource, identity, libraries or credential.
// Both laptop and omarchy-pc authenticate as the original writer subject using
// their own protected holonet-recommendations.app-password token; host identity
// selection never substitutes the host account or host.app-password.
func holonetLibraryContract() holonetContract {
	return holonetContract{
		username:       holonetWriterUsername,
		scope:          holonetLibraryScope,
		namespace:      "managed-library",
		libraries:      []string{"1132", "3", "615"},
		catalog:        []string{},
		targets:        []string{},
		history:        []string{},
		actions:        []string{"library.read", "library.manage"},
		writer:         true,
		originalWriter: true,
	}
}

func holonetLibraryMode(host string) {
	node, err := os.Hostname()
	if err != nil || ovFullBinding(host, node, os.Getuid()) != nil {
		fail()
	}
	contract := holonetLibraryContract()
	path, err := holonetCredentialPathFor(os.Getuid(), contract)
	if err != nil {
		fail()
	}
	password, err := readOVCredential(path, os.Getuid())
	if err != nil {
		fail()
	}
	ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
	defer cancel()
	token, err := acquireHolonetFor(ctx, httpClient(), password, time.Now, contract)
	if err != nil {
		fail()
	}
	emit(token)
}
