package main

// Closed acquisition purposes share the existing writer credential. No caller
// supplies scopes, actions, resource, identity, Series library or credential.
// Acquisition authority is enrolled for the original writer subject only, so the
// host identity selector never substitutes the host account or its credential.
func holonetAcquireContract(purpose string) holonetContract {
	scope := "holonet.read holonet.janitor holonet.acquire"
	actions := []string{"janitor.acquire.read"}
	switch purpose {
	case "start":
		scope += " holonet.acquire.start"
		actions = append(actions, "janitor.acquire.start")
	case "media":
		scope += " holonet.acquire.media"
		actions = append(actions, "janitor.acquire.media")
	case "read":
	default:
		panic("invalid internal acquisition purpose")
	}
	return holonetContract{username: holonetWriterUsername, scope: scope,
		namespace: "managed-janitor", libraries: []string{holonetDefaultLibrary},
		catalog: []string{}, targets: []string{}, history: []string{},
		actions: actions, writer: true, originalWriter: true}
}
