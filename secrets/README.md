# Secret references

Commit public SOPS+age encryption rules and references only. The public recipient
is in .sops.yaml; no private identity or credential content is inspected by CI.
A reference has exactly kind and path: encrypted uses a relative secrets/*.sops.yaml
path; local_file uses an absolute protected locally provisioned file path. Inline
payloads, extra fields, traversal, missing or ambiguous references are refused.
The default credential_references list is empty until operator mapping is confirmed.

Synthetic examples: {kind: encrypted, path: secrets/example.sops.yaml} and
{kind: local_file, path: /protected/example}. These are schema examples, not payloads.
Existing keys and credentials stay outside Git. Igor retains responsibility for
the offline age recovery copy, ciphertext recovery drill and decrypt authority.
Protected pointers do not authorize reading their contents. CI never decrypts
production ciphertext or issues credentials.
