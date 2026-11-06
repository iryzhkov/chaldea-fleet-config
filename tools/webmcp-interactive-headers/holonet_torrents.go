package main

const holonetTorrentsScope = "holonet.read holonet.janitor holonet.torrents"

// Separate Movies-only read grant on the existing writer identity.
func holonetTorrentsContract() holonetContract {
	return holonetContract{username: holonetWriterUsername, scope: holonetTorrentsScope,
		namespace: "managed-janitor", libraries: []string{holonetDefaultLibrary},
		catalog: []string{}, targets: []string{}, history: []string{},
		actions: []string{"janitor.torrents.read"}, writer: true}
}

func holonetTorrentsMode() {
	holonetJanitorModeFor(holonetTorrentsContract())
}
