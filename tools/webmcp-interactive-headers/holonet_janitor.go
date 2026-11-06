package main

import (
	"context"
	"os"
	"time"
)

const holonetJanitorScope = "holonet.read holonet.janitor"

// Independent fixed read contract on the existing writer account. No cohort,
// credential, library, action or scope is supplied by the caller.
func holonetJanitorContract() holonetContract {
	return holonetContract{username: holonetWriterUsername, scope: holonetJanitorScope,
		namespace: "managed-janitor", libraries: []string{holonetDefaultLibrary},
		catalog: []string{}, targets: []string{}, history: []string{},
		actions: []string{"janitor.importers.read", "janitor.custody.read"}, writer: true}
}

func holonetJanitorMode() {
	holonetJanitorModeFor(holonetJanitorContract())
}

// Both closed modes use the same bound credential and acquisition pipeline.
func holonetJanitorModeFor(contract holonetContract) {
	node, err := os.Hostname()
	if err != nil || holonetBinding(node, os.Getuid()) != nil {
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
	token, err := acquireHolonetFor(ctx, httpClient(), password, time.Now, contract)
	if err != nil {
		fail()
	}
	emit(token)
}
