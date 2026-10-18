// Fixed enrollment composition. Cryptographic/schema validation stays in Chaldea.
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const [client, policyFile, existingFile] = process.argv.slice(2);
const moduleAt = file => import(pathToFileURL(client + '/src/' + file));
const { publicKey, validateBundle } = await moduleAt('access/trust.ts');
const { helperConfig } = await moduleAt('access/helper.ts');
const { Authorization } = await moduleAt('akasha/auth.ts');
const { exact, object } = await moduleAt('access/token.ts');
const input = object(JSON.parse(readFileSync(0, 'utf8')));
exact(input, ['public_keys', 'pc_reader', 'pc_quota']);
if (typeof input.pc_reader !== 'boolean' || typeof input.pc_quota !== 'boolean') throw Error('boolean gates required');
const policy = JSON.parse(readFileSync(policyFile)), keys = object(input.public_keys);
exact(keys, Object.keys(policy));
for (const key of Object.values(keys)) publicKey(key);
if (new Set(Object.values(keys).map(k => k.x)).size !== 6) throw Error('host keys must differ');
const issuers = JSON.parse(readFileSync(existingFile)), original = structuredClone(issuers);
if (keys['agent-a'].x !== issuers[0].public_key.x) throw Error('agent-a reuse mismatch');
const grants = Object.fromEntries(Object.entries(policy).map(([host, row]) => [host, structuredClone(row.grants)]));
const pc = (action, source, kind, profile) => ({uid:1000, audience:'akasha', action, source, host:'omarchy-pc', kind, profile, project:'chaldea'});
if (input.pc_reader) for (const kind of ['feed_post', 'tool_call']) grants['omarchy-pc'].push(pc('read', 'fleet-reader', kind, 'fleet-reader'));
if (input.pc_quota) for (const kind of ['quota_parked', 'quota_reset_unknown', 'quota_resumed', 'restart_resumed', 'quota_headroom_snapshot', 'quota_headroom_changed', 'quota_headroom_low'])
  grants['omarchy-pc'].push(pc('append', 'chaldea-quota', kind, 'quota-service'));
const registry = [];
for (const [host, row] of Object.entries(policy)) {
  const issuer = {uid:row.issuer_uid, name:'chaldea:' + host, kid:row.kid, key_file:'/var/lib/chaldea-issuer/keys/' + row.kid + '.pem'};
  helperConfig({issuer, state_file:'/var/lib/chaldea-issuer/access/state.sqlite', bundle_file:'/var/lib/chaldea-access-trust-public/bundle.jws',
    anchor_file:'/etc/chaldea-access-trust/anchors.json', clock_health_file:'/run/chaldea-access-trust/clock-health.json', grants:grants[host]});
  let record = issuers.find(k => k.issuer === issuer.name && k.kid === row.kid);
  if (!record) { record = {issuer:issuer.name, kid:row.kid, public_key:keys[host], not_before:1792281600, issue_until:1794787200, verify_until:1794788010, ceilings:[]}; issuers.push(record); }
  for (const g of grants[host]) {
    const ceiling = {audience:g.audience, profile:g.profile, project:g.project, source:g.source, grants:[{resource:g.source, actions:[g.action]}]};
    if (!record.ceilings.some(c => JSON.stringify(c) === JSON.stringify(ceiling))) record.ceilings.push(ceiling);
    const known = original.some(k => k.issuer === issuer.name && k.ceilings.some(c => c.source === g.source && c.profile === g.profile && c.project === g.project));
    let entry = registry.find(r => r.issuer === issuer.name && r.source === g.source);
    if (!entry && !known) {
      entry = {issuer:issuer.name, source:g.source, host, source_id:(host + '--' + g.source).replaceAll('.', '_'), profile:g.profile, project:g.project,
        mode:g.action === 'read' ? 'operator' : 'service', kinds:[], ...(g.action === 'read' ? {global_read:true} : {})};
      registry.push(entry);
    }
    if (entry && !entry.kinds.includes(g.kind)) entry.kinds.push(g.kind);
  }
}
validateBundle({v:1, sequence:1, published_at:1792281600, expires_at:1792368000, keys:issuers});
new Authorization(registry, null, null);
process.stdout.write(JSON.stringify({issuers, registry, grants}));
