"""
ERI Type-2 subpackage — official ITD API integration (future production).

Modules here make real HTTPS calls to the ITD e-Filing gateway. They are
mode-guarded: when ``ERI_MODE != "type2"``, the Type-2 routes return 503
and these modules are not exercised.

Type-2 architecture (per DUAL_MODE_ERI_INTEGRATION_PLAN.md §6):
  - LocalSigner  (app/eri/type2/local_signer.py)    — USB DSC, NEXT SEASON
  - AwsDispatcher (app/eri/type2/aws_dispatcher.py)  — SSH dispatch, NEXT SEASON
  - submit flow   (app/eri/type2/submit.py)          — NEXT SEASON

This season, the existing login/add_client/prefill/everify/acknowledgement
modules remain as-is (moved here from app/eri/), behind the mode guard.
"""
