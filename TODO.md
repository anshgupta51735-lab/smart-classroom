# Fix Code Errors & Remove Duplicates - Progress Tracker

## Plan Steps:
- [ ] Step 1: Fix FastAPI.py (remove duplication, deprecated lifespan, DB path)
- [ ] Step 2: Fix config.py (API_BASE_URL to localhost)
- [ ] Step 3: Fix api_client.py (remove duplicate, keep pi_agent version)
- [x] Step 4: Fix pi_agent.py (absolute imports) - Complete ✓
  - [x] Update pi_agent.py imports
  - [x] Test run (now GPIO error, normal for dev)
- [x] Step 5: Clean pir_sensor.py, relay_controller.py, rfid_reader.py (remove old versions) - Complete ✓
  - [x] Clean rfid_reader.py (remove duplicates)
  - [x] Clean pir_sensor.py (remove duplicates, fix imports/syntax)
  - [x] Clean relay_controller.py (remove duplicates)
- [ ] Step 6: Fix smartedu_pulse.py (remove duplicate DB flag)
- [ ] Step 7: Test: uvicorn + python pi_agent.py + streamlit
- [ ] Step 8: Complete

**Status: Pi agent errors fixed and support files cleaned. Ready for Step 1 or full test?**
