# model-discovery / api — TODO

Living list of hardening work. Grouped by area, ordered loosely by priority
within each group. Tick items off as they land.

---

## 1. Upload backend

The `LocalFileUploadClient` writes directly to the iRODS PVC. It is a
stand-in until a real upload service exists. Things to do before relying
on it for anything beyond dev/POC:

- [ ] **Replace with a real upload service** when one is ready. Flip
      `UPLOAD_BACKEND=http` (already wired) — no API changes needed.
- [ ] **Sessions are in-memory.** A pod restart loses every in-flight
      upload. Either (a) accept that and require clients to retry, (b)
      persist session state to disk under `{mount}/.uploads/sessions/`,
      or (c) require single-replica when `UPLOAD_BACKEND=local`.
- [ ] **No multi-replica safety.** Two pods will each have their own
      session map; sticky sessions or shared state required if we scale
      out the gateway with the local backend. Document this in the chart
      values.
- [ ] **No upload TTL / GC.** Abandoned `.uploads/*.part` files stay
      forever. Add a periodic sweep (e.g. delete `.part` files older
      than 24h) or clean up on the next `init_upload` for the same
      resource.
- [ ] **No size limit.** Add a per-upload byte cap and reject early in
      `init_upload` (probably configurable via `MAX_UPLOAD_BYTES`). Today
      a malicious client can fill the PVC.
- [ ] **No content-type validation.** We accept whatever the client
      claims. For datasets/models, decide whether to enforce known
      MIME types or scan files (see Security).
- [ ] **Filename charset is conservative** (`[A-Za-z0-9._-]`). Real-world
      filenames often have spaces / unicode — widen the allowed set
      after deciding on a normalization rule, or generate an internal
      filename and store the original in metadata.
- [ ] **Out-of-order parts rejected.** Fine for our endpoint (which
      uploads in order) but a future S3-style direct-from-browser flow
      will need real multipart with a parts index + final assembly.
- [ ] **No checksum verification.** Add SHA-256 (or MD5) computation
      during write and a `digest` field in `UploadAcceptedResponse` so
      clients can verify integrity. Tie it to the registry's
      `digest_sha256` resource field.

## 2. Resource ↔ upload coupling

Right now an upload lands at `{mount}/{resource_id}/{filename}`, but
nothing enforces that a registry resource with that id exists, or that
its `location_uri` actually points there.

- [ ] **Validate `resource_id` against the registry** in
      `upload_resource_file` (404 if no resource).
- [ ] **Auto-set or validate `location_uri`** on the registered
      resource the first time a file is uploaded for it (e.g. set to
      `irods:///{resource_id}` if currently empty; reject if it points
      somewhere else).
- [ ] **Authorization check**: only the resource owner (or a designated
      role) can upload files. Today any authenticated principal can
      overwrite anything.
- [ ] **Overwrite policy**: today re-uploading the same filename
      replaces it via `os.replace`. Decide whether that is intended;
      consider versioning files alongside the immutable-resource model.

## 3. Download endpoint

- [ ] **Streaming zip uses `_StreamingBuffer`** — works, but a single
      huge member still blocks the event loop while compressing. Move
      `zentry.write` into a thread or switch to `stream-zip`.
- [ ] **No range-request support** for single-file download. Adding
      `Range:` lets browsers resume large pulls and `<video>` elements
      seek.
- [ ] **No content-disposition charset handling**. Filenames with
      unicode will mangle on some clients (use `filename*=UTF-8''…`).
- [ ] **No download throttling / quota**. Trivial DoS surface if the
      PVC is large.

## 4. Auth / authz

- [ ] **Add RBAC** (or fine-grained authz, e.g. OpenFGA) on resources.
      Hooks marked `# FUTURE: fga.write_tuple(...)` and
      `# FUTURE: fga.check(...)` already exist in `RegistryService`.
- [ ] **Audit log** for upload, download, run create/cancel, model
      register/update.
- [ ] **Per-resource ownership transfer flow**.

## 5. Execution proxy

- [ ] **`GET /runs/{id}` always refreshes** unless `?refresh=false`.
      Consider adding an *exec-cache TTL* on the gateway side so the UI
      polling 5×/sec doesn't hammer the exec service.
- [ ] **Run cancellation idempotency**: confirm the exec service
      treats DELETE on an already-terminal run as a no-op.
- [ ] **Bulk run-status fetch** — `?refresh=true` on
      `GET /models/{id}/runs` would pre-fetch fresh statuses for all
      listed runs instead of N round-trips.

## 6. Storage abstraction

`core/file_storage.py` knows only about iRODS-on-PVC. To support S3 /
LakeFS / GCS without ripping it apart:

- [ ] **Introduce a `Storage` protocol** with `list_files`, `read_file`,
      `write_file`, `delete_file`. Have `LocalFileUploadClient`,
      download endpoints, and `RegistryService.get_resource_directory`
      depend on the protocol, not on `Path`.
- [ ] **Plug an S3 backend** behind it once we move off of PVC.
- [ ] **Plug iRODS-native backend** (over the protocol library, not the
      mount) to reduce blast-radius of PVC mount issues.

## 7. Observability

- [ ] **Structured logs** — already mostly there, but verify every
      logger call has request-id and resource/run id where applicable.
- [ ] **Prometheus metrics** for upload bytes, download bytes, run
      create/cancel latency, exec proxy latency.
- [ ] **OpenTelemetry traces** end-to-end (UI → gateway → exec).

## 8. Tests

- [ ] **Integration test** that exercises POST upload → GET list →
      GET download in one flow against the same temp mount, end-to-end
      via TestClient.
- [ ] **Concurrent upload race test** — two sessions writing to the
      same `{resource_id}/{filename}` simultaneously; assert atomic
      rename wins cleanly.
- [ ] **Failure-injection** for `os.fsync` / `os.replace` (mock raising
      `OSError`) to lock in the cleanup-on-error behavior.
- [ ] **Path-traversal fuzz** for `_validate_resource_id` /
      `_sanitize_filename` (hypothesis would be overkill; a parametrize
      list of OWASP-style payloads is enough).

## 9. Docs / DX

- [ ] **Document the local-upload layout** in the chart `values.yaml`
      comments.
- [ ] **Add a CONTRIBUTING.md** snippet describing how to flip
      `UPLOAD_BACKEND` in dev.
- [ ] **OpenAPI examples** for `POST /resources/{id}/files`, including
      the multipart body shape.
