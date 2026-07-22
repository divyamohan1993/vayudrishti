"""Publish layer (owner: vayu-models).

- ``sanitize``: publish-time string cleaning + strict gate validators (spec 7).
- ``contentmodels``: pydantic content models mirroring config/schemas/*.json. These
  ARE the emit contract: ``vayu publish`` constructs them, so it cannot emit
  schema/range/sanitization/invariant-invalid data. ``vayu gate`` re-reads emitted
  files and constructs the same strict models, rejecting any tampered or malformed
  file (acceptance 13).
- ``emit``: serialize a validated model to its web/public/data path.
- ``gate``: file-scanning content gate used by CI and by publish's final step.
"""
