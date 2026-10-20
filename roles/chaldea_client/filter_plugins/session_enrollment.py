"""Closed public enrollment validation. No filesystem, credentials or network access."""
import re
from collections.abc import Mapping
from posixpath import normpath
from urllib.parse import urlsplit

from ansible.errors import AnsibleFilterError


COMMON = {"form", "issuer", "tokenUrl", "jwksUrl", "clientId", "username",
          "resource", "scope", "maxTokenSeconds", "secretFile"}
FIELDS = {"ov": {"ov_namespaces"}, "homelab": {"homelab_services", "homelab_hosts"},
          "ha": {"ha_entities", "ha_actions"}}
RESOURCES = {a: "https://" + a + ".mcp.ryzhkov.dev/mcp" for a in FIELDS}
HA_SCOPES = {"ha.read", "ha.control", "ha.read ha.control", "ha.control ha.read"}
ACTIONS = {"state.read": "ha.read", "light.control": "ha.control", "switch.control": "ha.control"}
CANONICAL = (r"https://[a-z0-9]([a-z0-9-]*[a-z0-9])?"
             r"([.][a-z0-9]([a-z0-9-]*[a-z0-9])?)*"
             r"(:(?!443/)[0-9]{1,5})?/[A-Za-z0-9._~!$&'()*+,;=:@%/-]*")


def require(condition, field):
    if not condition:
        raise AnsibleFilterError("Enrollment/session policy refused: " + field)


def matches(value, pattern):
    return isinstance(value, str) and re.fullmatch(pattern, value, re.ASCII) is not None


def explicit_list(value, minimum, maximum, pattern, field):
    require(isinstance(value, list) and minimum <= len(value) <= maximum, field)
    require(all(matches(v, pattern) for v in value), field)
    require(len(set(value)) == len(value), field)
    return value


def origin(url):
    parts = urlsplit(url)
    return parts.scheme + "://" + parts.netloc


def canonical(url, strict=False):
    require(matches(url, CANONICAL), "canonical HTTPS URL")
    if strict:
        parts = urlsplit(url)
        try:
            port = parts.port
        except ValueError as exc:
            raise AnsibleFilterError("Enrollment/session policy refused: URL port") from exc
        require(port is None or (0 < port <= 65535 and str(port) == parts.netloc.rsplit(":", 1)[1]),
                "URL port")
        segments = parts.path.split("/")[1:]
        require("%" not in url and all(s not in {".", ".."} for s in segments)
                and all(segments[:-1]), "canonical provider path")


def service(value):
    require(isinstance(value, Mapping), "service object")
    audience = value.get("audience")
    require(isinstance(audience, str) and audience in FIELDS, "closed audience")
    require(set(value) == {"audience", "scope"} | FIELDS[audience], "closed service fields")
    scope = value["scope"]
    if audience == "ov":
        require(scope == "ov.read", "OV scope")
        roots = explicit_list(value["ov_namespaces"], 1, 16,
                              r"viking://resources/[A-Za-z0-9_@+.,=-]+(/[A-Za-z0-9_@+.,=-]+)*",
                              "OV roots")
        require(all(len(r) <= 1024 and all(s not in {".", ".."} for s in r[19:].split("/"))
                    for r in roots), "OV canonical roots")
        require(not any(a != b and b.startswith(a + "/") for a in roots for b in roots),
                "OV overlapping roots")
    elif audience == "homelab":
        require(scope == "homelab.read", "homelab scope")
        for key in FIELDS[audience]:
            explicit_list(value[key], 0, 128, r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", key)
    else:
        require(isinstance(scope, str) and scope in HA_SCOPES, "HA scope")
        entities = explicit_list(value["ha_entities"], 1, 64,
                                 r"(light|switch|sensor|binary_sensor)\.[a-z0-9_]{1,96}", "HA entities")
        require(all(len(e) <= 112 for e in entities), "HA entity length")
        actions = explicit_list(value["ha_actions"], 1, 3,
                                r"state\.read|light\.control|switch\.control", "HA actions")
        require(all(ACTIONS[a] in scope.split(" ") for a in actions), "HA action scope")
    return value


def subset(request, ceiling):
    if request["audience"] != ceiling["audience"]:
        return False
    audience = request["audience"]
    if audience == "ov":
        return all(any(r == c or r.startswith(c + "/") for c in ceiling["ov_namespaces"])
                   for r in request["ov_namespaces"])
    if audience == "homelab":
        return all(set(request[k]) <= set(ceiling[k]) for k in FIELDS[audience])
    return (set(request["scope"].split(" ")) <= set(ceiling["scope"].split(" "))
            and all(set(request[k]) <= set(ceiling[k]) for k in FIELDS[audience]))


def typed_services(values):
    require(isinstance(values, list), "services list")
    typed = []
    for value in values:
        require(isinstance(value, Mapping), "service object")
        # The old grants codec remains parse-only, including in ceilings.
        if "grants" in value:
            require(set(value) == {"audience", "grants"}, "legacy service fields")
        else:
            typed.append(service(value))
    return typed


def chaldea_session_enrollments(enrollments, presets, ceilings, home):
    require(isinstance(enrollments, Mapping) and isinstance(presets, Mapping)
            and isinstance(ceilings, list), "policy maps")
    parsed_ceilings = []
    for ceiling in ceilings:
        require(isinstance(ceiling, Mapping), "ceiling object")
        parsed_ceilings.append((ceiling, typed_services(ceiling.get("services"))))
    for key, preset in presets.items():
        typed = typed_services(preset.get("services"))
        if not typed:
            continue
        require(len(preset["services"]) == 1 and len(typed) == 1, "one service per new preset")
        require(key in enrollments, "new preset needs enrollment")
        request = typed[0]
        require(any(c.get("project") == preset.get("project")
                    and isinstance(c.get("maxSeconds"), int) and not isinstance(c["maxSeconds"], bool)
                    and isinstance(preset.get("maxSeconds"), int) and not isinstance(preset["maxSeconds"], bool)
                    and 0 < preset["maxSeconds"] <= c["maxSeconds"]
                    and isinstance(preset.get("destinations"), list)
                    and isinstance(c.get("destinations"), list)
                    and all(d in c["destinations"] for d in preset["destinations"])
                    and any(subset(request, s) for s in services)
                    for c, services in parsed_ceilings), "one admitting ceiling")
    identities = []
    for key, value in enrollments.items():
        require(key in presets and isinstance(value, Mapping), "declared preset enrollment")
        preset = presets[key]
        new = "audience" in value
        if new:
            audience = value["audience"]
            require(isinstance(audience, str) and audience in FIELDS, "closed audience")
            require(set(value) == COMMON | {"audience"} | FIELDS[audience], "closed enrollment fields")
            grant = service({k: value[k] for k in {"audience", "scope"} | FIELDS[audience]})
            require(preset["services"] == [grant], "exact preset/enrollment payload")
            require(value["resource"] == RESOURCES[audience], "fixed resource")
        else:
            audience = "jocasta"
            require(set(value) == COMMON | {"project"}, "legacy enrollment fields")
            require(value["scope"] == "jocasta.read" and value["project"] == preset["project"],
                    "legacy Jocasta project/scope")
            jocasta = [s for s in preset["services"] if s.get("audience") == "jocasta"]
            require(len(jocasta) == 1 and isinstance(jocasta[0].get("grants"), list)
                    and bool(jocasta[0]["grants"])
                    and all(g.get("resource") == "project:" + value["project"]
                            for g in jocasta[0]["grants"]), "legacy Jocasta grant")
        require(value["form"] == "app_password" and isinstance(value["maxTokenSeconds"], int)
                and not isinstance(value["maxTokenSeconds"], bool)
                and value["maxTokenSeconds"] == 300, "app_password lifetime")
        require(matches(value["clientId"], r"[\x21-\x7e]{1,255}"), "clientId")
        require(matches(value["username"], r"[A-Za-z0-9][A-Za-z0-9._@-]{0,149}"), "username")
        for field in ("issuer", "tokenUrl", "jwksUrl", "resource"):
            canonical(value[field], strict=new)
        require(origin(value["tokenUrl"]) == origin(value["issuer"])
                and origin(value["jwksUrl"]) == origin(value["issuer"]), "issuer origin")
        if new:
            require(value["issuer"].endswith("/")
                    and value["jwksUrl"] == value["issuer"] + "jwks/"
                    and value["tokenUrl"] == origin(value["issuer"]) + "/application/o/token/",
                    "exact provider URLs")
        require(value["secretFile"] == home + "/.config/chaldea/authentik/" + key + ".app-password"
                and normpath(value["secretFile"]) == value["secretFile"], "per-preset secretFile")
        identity = (new, audience, origin(value["issuer"]), value)
        for old_new, old_audience, old_origin, old in identities:
            if not (new or old_new):
                continue
            require(value["secretFile"] != old["secretFile"], "isolated secretFile")
            if old_origin == identity[2]:
                require(value["username"] != old["username"], "isolated ordinary account")
                if audience != old_audience:
                    require(value["issuer"] != old["issuer"] and value["clientId"] != old["clientId"],
                            "distinct service provider/client")
        identities.append(identity)
    return True


def chaldea_session_policy_size(rendered):
    # Same 64 KiB whole-file ceiling as the authoritative client policy-load preflight.
    require(isinstance(rendered, str) and len(rendered.encode("utf-8")) <= 64 * 1024,
            "rendered policy exceeds 64 KiB")
    return True


class FilterModule:
    def filters(self):
        return {"chaldea_session_enrollments": chaldea_session_enrollments,
                "chaldea_session_policy_size": chaldea_session_policy_size}
