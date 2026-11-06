package main

const holonetSeedJoinScope = "holonet.read holonet.janitor holonet.seedjoin"

// Separate Movies-only read grant on the existing writer identity.
func holonetSeedJoinContract() holonetContract {
	return holonetContract{username: holonetWriterUsername, scope: holonetSeedJoinScope,
		namespace: "managed-janitor", libraries: []string{holonetDefaultLibrary},
		catalog: []string{}, targets: []string{}, history: []string{},
		actions: []string{"janitor.seed_join.read"}, writer: true}
}

func holonetSeedJoinMode() {
	holonetJanitorModeFor(holonetSeedJoinContract())
}
