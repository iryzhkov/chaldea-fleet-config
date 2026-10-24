"""Read only protected controller enrollment files; never quote contents/errors."""
import json
import os
import stat

from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase


def protected_read(path, host):
    if not isinstance(path, str) or not path.startswith("/") or os.path.normpath(path) != path:
        raise ValueError()
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        parts = path[1:].split("/")
        for part in parts[:-1]:
            st = os.fstat(fd)
            if st.st_uid not in (0, os.getuid()) or st.st_mode & 0o022:
                raise ValueError()
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        st = os.fstat(fd)
        if st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) != 0o700:
            raise ValueError()
        leaf = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=fd)
        with os.fdopen(leaf) as stream:
            st = os.fstat(stream.fileno())
            if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) != 0o600 or not 1 <= st.st_size <= 4096:
                raise ValueError()
            data = stream.read(4097)
            after = os.fstat(stream.fileno())
            if len(data) > 4096 or (st.st_mtime_ns, st.st_size) != (after.st_mtime_ns, after.st_size):
                raise ValueError()
        def unique(pairs):
            obj = {}
            for key, value in pairs:
                if key in obj:
                    raise ValueError()
                obj[key] = value
            return obj
        value = json.loads(data, object_pairs_hook=unique)
        if (set(value) != {"version", "owner", "host", "username", "password", "generation"}
                or value["version"] != 1 or value["host"] != host
                or value["username"] != "webmcp-interactive-" + host
                or type(value["generation"]) is not int or not 1 <= value["generation"] <= 1000
                or not isinstance(value["owner"], str) or len(value["owner"]) != 36
                or not isinstance(value["password"], str) or not 16 <= len(value["password"]) <= 256
                or any(ord(c) < 33 or ord(c) > 126 for c in value["password"])):
            raise ValueError()
        return data
    finally:
        os.close(fd)


class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        try:
            if len(terms) != 2:
                raise ValueError()
            return [protected_read(*terms)]
        except Exception:
            raise AnsibleError("managed enrollment input unavailable or unsafe") from None
