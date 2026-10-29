-- The XMPP server the line's agents talk through (line-agents; docs/agents.md). One virtual host,
-- "localhost": an agent is <name>@localhost and registers its own account on its first start
-- (in-band registration, as SPADE does with auto_register). For the lab network only: no TLS
-- required, accounts kept in Prosody's own files (the volume prosody-data).
admins = { }
modules_enabled = {
    "roster"; "saslauth"; "tls"; "disco"; "ping"; "register"; "posix";
}
allow_registration = true
-- Agents register many accounts from one address (the agent host): no throttling.
min_seconds_between_registrations = 0
registration_throttle_max = nil
c2s_require_encryption = false
s2s_require_encryption = false
allow_unencrypted_plain_auth = true
authentication = "internal_hashed"
storage = "internal"
log = { info = "*console" }
pidfile = "/var/run/prosody/prosody.pid"

VirtualHost "localhost"
