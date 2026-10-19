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
exact(input, ['public_keys', 'pc_reader', 'pc_quota'], ['laptop_quota', 'pc_quota_reader', 'mission_control']);
if (typeof input.pc_reader !== 'boolean' || typeof input.pc_quota !== 'boolean' ||
    ['laptop_quota', 'pc_quota_reader'].some(k => input[k] !== undefined && typeof input[k] !== 'boolean')) throw Error('boolean gates required');
const policy = JSON.parse(readFileSync(policyFile)), keys = object(input.public_keys);
exact(keys, Object.keys(policy));
for (const key of Object.values(keys)) publicKey(key);
if (new Set(Object.values(keys).map(k => k.x)).size !== 6) throw Error('host keys must differ');
const issuers = JSON.parse(readFileSync(existingFile));
if (keys['agent-a'].x !== issuers[0].public_key.x) throw Error('agent-a reuse mismatch');
const grants = Object.fromEntries(Object.entries(policy).map(([host, row]) => [host, structuredClone(row.grants)]));
const pc = (action, source, kind, profile) => ({uid:1000, audience:'akasha', action, source, host:'omarchy-pc', kind, profile, project:'chaldea'});
if (input.pc_reader) for (const kind of ['feed_post', 'tool_call']) grants['omarchy-pc'].push(pc('read', 'fleet-reader', kind, 'fleet-reader'));
if (input.pc_quota) for (const kind of ['quota_parked', 'quota_reset_unknown', 'quota_resumed', 'restart_resumed', 'quota_headroom_snapshot', 'quota_headroom_changed', 'quota_headroom_low'])
  grants['omarchy-pc'].push(pc('append', 'chaldea-quota', kind, 'quota-service'));
// Sharing is a separate service permission, never an operator/global reader.
if (input.laptop_quota) grants['omarchy-macbook-air-igor'].push({uid:1001, audience:'akasha', action:'append', source:'quota',
  host:'omarchy-macbook-air-igor', kind:'quota_headroom_snapshot', profile:'quota-service', project:'chaldea'});
if (input.pc_quota_reader) grants['omarchy-pc'].push(pc('read', 'quota', 'quota_headroom_snapshot', 'quota-service'));
// Explicit permission packet, independent of all installation/enablement flags.
if (input.mission_control !== undefined) {
  const mc = object(input.mission_control);
  exact(mc, ['publisher_uid', 'reader_uid', 'read_sources'], ['pc_publisher_uid']);
  const pcUid = mc.pc_publisher_uid ?? null;
  if (pcUid !== null && pcUid !== 1000) throw Error('existing PC collector UID must be 1000');
  if (mc.publisher_uid !== null && mc.publisher_uid !== 1000) throw Error('agent-a publisher UID must be 1000');
  if (mc.reader_uid !== null && (!Number.isSafeInteger(mc.reader_uid) || mc.reader_uid <= 0 ||
      mc.reader_uid >= 4294967295 || [957, 995, 1000, 1001].includes(mc.reader_uid))) throw Error('dedicated reader UID required');
  if (!Array.isArray(mc.read_sources) || mc.read_sources.length > 4 ||
      new Set(mc.read_sources).size !== mc.read_sources.length ||
      mc.read_sources.some(s => !['agent-a--mission-control', ...(pcUid === null ? [] : ['omarchy-pc--mission-control'])].includes(s)) ||
      (pcUid !== null && (mc.publisher_uid !== 1000 || mc.reader_uid === null ||
        JSON.stringify(mc.read_sources) !== JSON.stringify(['agent-a--mission-control', 'omarchy-pc--mission-control']))) ||
      (mc.reader_uid === null) !== (mc.read_sources.length === 0)) throw Error('exact reader source selection required');
  if (mc.publisher_uid !== null) grants['agent-a'].push({uid:1000, audience:'akasha', action:'append',
    source:'agent-a.mission-control', host:'agent-a', kind:'agent_status', profile:'mission-control-publisher', project:'chaldea'});
  if (pcUid !== null) grants['omarchy-pc'].push(pc('append', 'omarchy-pc.mission-control', 'agent_status', 'mission-control-publisher'));
  if (mc.reader_uid !== null) grants['omarchy-normandy'].push({uid:mc.reader_uid, audience:'akasha', action:'read',
    source:'mission-control-reader', host:'omarchy-normandy', kind:'agent_status', profile:'mission-control-reader', project:'chaldea'});
}
const registry = [];
for (const [host, row] of Object.entries(policy)) {
  const issuer = {uid:row.issuer_uid, name:'chaldea:' + host, kid:row.kid, key_file:'/var/lib/chaldea-issuer/keys/' + row.kid + '.pem'};
  helperConfig({issuer, state_file:'/var/lib/chaldea-issuer/access/state.sqlite', bundle_file:'/var/lib/chaldea-access-trust-public/bundle.jws',
    anchor_file:'/etc/chaldea-access-trust/anchors.json', clock_health_file:'/run/chaldea-access-trust/clock-health.json', grants:grants[host]});
  let record = issuers.find(k => k.issuer === issuer.name && k.kid === row.kid);
  if (record && record.public_key.x !== keys[host].x) throw Error('existing signer public mismatch');
  if (!record) { record = {issuer:issuer.name, kid:row.kid, public_key:keys[host], not_before:1792281600, issue_until:1794787200, verify_until:1794788010, ceilings:[]}; issuers.push(record); }
  for (const g of grants[host]) {
    const ceiling = {audience:g.audience, profile:g.profile, project:g.project, source:g.source, grants:[{resource:g.source, actions:[g.action]}]};
    if (!record.ceilings.some(c => JSON.stringify(c) === JSON.stringify(ceiling))) record.ceilings.push(ceiling);
    const known = host === 'agent-a' && ['agent-a.fleet', 'agent-a.toolfeedback'].includes(g.source);
    let entry = registry.find(r => r.issuer === issuer.name && r.source === g.source);
    if (!entry && !known) {
      entry = {issuer:issuer.name, source:g.source, host, source_id:g.profile === 'mission-control-publisher' && g.source === host + '.mission-control' ? host + '--mission-control' : (host + '--' + g.source).replaceAll('.', '_'), profile:g.profile, project:g.project,
        mode:g.action === 'read' && !['quota', 'mission-control-reader'].includes(g.source) ? 'operator' : 'service', kinds:[],
        ...(g.action === 'read' ? (g.source === 'mission-control-reader' ? {mission_control_read_sources:input.mission_control.read_sources} : g.source === 'quota' ? {quota_fleet_read:true} : {global_read:true}) : {})};
      registry.push(entry);
    }
    if (entry && !entry.kinds.includes(g.kind)) entry.kinds.push(g.kind);
  }
}
validateBundle({v:1, sequence:1, published_at:1792281600, expires_at:1792368000, keys:issuers});
new Authorization(registry, null, null);
process.stdout.write(JSON.stringify({issuers, registry, grants}));
