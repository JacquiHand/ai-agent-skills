-- deploy-website-route.sql
--
-- Bootstraps a static-file VHOST route for an already-published website
-- (see references/isql-route-mode.md). This does NOT upload any content —
-- run scripts/publish_static_bundle.py separately (before or after this
-- script; the route and the files are independent of each other).
--
-- Literal find/replace before running, same convention as
-- weblog-from-webdav's deploy-*.sql templates (no {{token}} engine):
--   /DAV/home/kidehen/sites/openlink/   -> your target DAV collection (must end in /)
--   linkeddata.uriburner.com            -> your target virtual host
--   /sites/openlink/                    -> your desired public route path (must end in /)
--   OpenLink Portfolio Site             -> a human-readable title, used only in the
--                                          verification output below, not deployed anywhere
--
-- Run with: isql <host>:<port> <user> <password> deploy-website-route.sql
-- or, for WebID-TLS: isql <host>:<port> "" "$P12_PASSWORD" -X <cert.p12> -T <ca.pem>
--   -W '<delegated-webid>' deploy-website-route.sql

-- 1. Remove any prior conflicting VHOST_DEFINE for this host/path before
--    redefining it. Never leave two competing route definitions.
DB.DBA.VHOST_REMOVE (
  lhost => 'linkeddata.uriburner.com',
  vhost => 'linkeddata.uriburner.com:443',
  lpath => '/sites/openlink/'
);

-- 2. Define the static-file route. is_dav=>1 with def_page=>'index.html'
--    serves plain files from the DAV collection -- no VSP execution.
--    Do NOT set def_page=>'index.vsp' unless a VSP entry point genuinely
--    exists at that path; pointing def_page at a nonexistent VSP resource
--    serves raw source or a 404, not the site.
DB.DBA.VHOST_DEFINE (
  lhost       => 'linkeddata.uriburner.com',
  vhost       => 'linkeddata.uriburner.com:443',
  lpath       => '/sites/openlink/',
  ppath       => '/DAV/home/kidehen/sites/openlink/',
  is_dav      => 1,
  is_brws     => 0,
  def_page    => 'index.html',
  vsp_user    => 'dba',
  ses_vars    => 0,
  opts        => vector ('browse_sheet', '', 'noinherit', 'yes'),
  is_default_host => 0
);

-- 3. Verification -- run in the same isql session so the output itself is
--    evidence the route exists. Confirms the intended path and that the
--    target DAV collection is a real, resolvable resource.
SELECT HP_LISTEN_HOST, HP_HOST, HP_LPATH, HP_PPATH, HP_DEF_PAGE
  FROM DB.DBA.HTTP_PATH
  WHERE HP_LPATH = '/sites/openlink/';

SELECT COUNT(*) AS collection_resource_count
  FROM WS.WS.SYS_DAV_RES
  WHERE RES_FULL_PATH LIKE '/DAV/home/kidehen/sites/openlink/%';

-- Expect: one HTTP_PATH row with HP_PPATH matching the DAV collection above
-- and HP_DEF_PAGE = 'index.html'; collection_resource_count > 0 once
-- publish_static_bundle.py has run. A zero count here with an otherwise
-- correct route means the route was bootstrapped before publishing --
-- not an error, just run the publish script next.
