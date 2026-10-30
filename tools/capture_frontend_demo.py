"""Capture REAL HA frontend with SYNTHETIC data; run only after run_frontend_demo.

Optional development tool. Playwright is not an integration dependency.
Overwrites the named documentation PNGs, never connects to Mitsubishi.
"""

import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from custom_components.melcloud_diagnostics.const import VERSION
from custom_components.melcloud_diagnostics.core.test_session import validate_report

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "docs/images"
DEMO = ROOT / ".tools/frontend-ha"


def main():
    from playwright.sync_api import sync_playwright

    if not (DEMO / "SYNTHETIC_DEMO_ONLY").exists():
        raise RuntimeError("Start the isolated synthetic harness first")
    auth = json.loads((DEMO / "browser-auth.json").read_text(encoding="utf-8"))
    ready = json.loads((DEMO / "ready.json").read_text(encoding="utf-8"))
    if not ready.get("synthetic") or auth["hassUrl"] != "http://127.0.0.1:18123":
        raise RuntimeError("Refusing a non-demo target")
    base = auth["hassUrl"]
    (DEMO / "capture-results.json").unlink(missing_ok=True)
    headers = {"Authorization": "Bearer " + auth["access_token"]}
    evidence = {"synthetic": True, "real_mitsubishi_account": False, "screenshots": []}
    with sync_playwright() as playwright:
        api = playwright.request.new_context(base_url=base, extra_http_headers=headers)

        def control(action="inspect", minutes=None):
            data = {"action": action}
            if minutes is not None:
                data["minutes"] = minutes
            response = api.post("/api/services/frontend_demo/control?return_response", data=data)
            if not response.ok:
                raise RuntimeError("Demo API failed; restart harness to renew temporary auth")
            value = response.json()["service_response"]
            if not value.get("synthetic"):
                raise RuntimeError("Refusing a non-synthetic server")
            return value

        def open_browser():
            browser = playwright.chromium.launch()
            context = browser.new_context(
                viewport={"width": 1440, "height": 1000},
                locale="it-IT",
                color_scheme="light",
                reduced_motion="reduce",
                accept_downloads=True,
            )
            context.add_init_script(
                'localStorage.setItem("hassTokens", ' + json.dumps(json.dumps(auth)) + ");"
                'localStorage.setItem("selectedLanguage", JSON.stringify("it"));'
            )
            context.route(
                "**/*",
                lambda route: (
                    route.continue_()
                    if urlsplit(route.request.url).hostname in ("127.0.0.1", None)
                    else route.abort()
                ),
            )
            page = context.new_page()
            page.set_default_timeout(20000)
            return browser, context, page

        browser, context, page = open_browser()

        def config_menu():
            page.goto(base + "/config/integrations/integration/melcloud_diagnostics")
            page.get_by_role("button", name="Configura", exact=True).click()

        def start(duration=3600, capture_start=False):
            config_menu()
            menu = page.locator("step-flow-menu")
            menu.get_by_text("Diagnostica", exact=True).click()
            menu.get_by_text("Collaudo diagnostico", exact=True).click()
            page.get_by_role(
                "radio",
                name="20 minuti — rapido" if duration == 1200 else "60 minuti — completo",
                exact=True,
            ).click()
            if capture_start:
                capture("diagnostics-collaudo-start.png")
            page.get_by_text(
                "Ho conservato il report precedente e ne autorizzo la sostituzione", exact=True
            ).click()
            page.get_by_role("button", name="Invia", exact=True).click()
            page.get_by_text("Aggiorna stato (solo locale)", exact=True).wait_for()
            page.get_by_role("button", name="Chiudi", exact=True).click()

        def diagnostic_view():
            stats = control()
            # Match frontend Date to the harness's accelerated time, without
            # replacing any sensor state, DOM content or progress calculation.
            page.clock.set_system_time(datetime.fromisoformat(stats["now"]))
            page.goto(base + "/lovelace/diagnostica")
            page.get_by_text("Avanzamento temporale", exact=True).wait_for()
            page.get_by_text("Storico errori", exact=True).wait_for()
            page.wait_for_timeout(400)
            return stats

        def capture(name):
            # Write a separate file first: Windows previewers/antivirus can hold
            # the previous PNG open through WSL. Never truncate the published copy.
            temporary = DEMO / name
            page.screenshot(path=str(temporary), full_page=True)
            temporary.replace(IMAGES / name)
            evidence["screenshots"].append(name)

        def download(name, status):
            page.goto(base + "/config/integrations/integration/melcloud_diagnostics")
            page.get_by_role("button", name="Configura", exact=True).wait_for()
            page.get_by_role("button", name="Menu", exact=True).nth(1).click()
            with page.expect_download(timeout=30000) as event:
                page.get_by_role("menuitem", name="Scarica la diagnostica", exact=True).click()
            path = DEMO / ("download-" + name + ".json")
            event.value.save_as(str(path))
            report = validate_report(
                json.loads(path.read_text(encoding="utf-8"))["data"]["diagnostic_test"]
            )
            assert report["session"]["status"] == status and report["session"]["read_only"]
            assert report["environment"]["integration"] == VERSION
            assert "11111111-1111-4111-8111-111111111111" not in json.dumps(report)
            return report

        try:
            start(capture_start=True)
            assert control()["status"] == "in_esecuzione"
            browser.close()
            control("advance", 5)
            evidence["continues_with_browser_closed"] = control()["status"] == "in_esecuzione"
            browser, context, page = open_browser()
            control("advance", 20)
            diagnostic_view()
            assert page.locator("hui-bar-gauge-card-feature").count() == 1
            capture("diagnostics-collaudo-running.png")
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(300)
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
            capture("diagnostics-collaudo-running-mobile.png")
            page.emulate_media(color_scheme="dark")
            page.wait_for_timeout(300)
            capture("diagnostics-collaudo-running-mobile-dark.png")
            page.set_viewport_size({"width": 1440, "height": 1000})
            page.wait_for_timeout(300)
            capture("diagnostics-collaudo-running-dark.png")
            page.emulate_media(color_scheme="light")
            control("advance", 35)
            stats = diagnostic_view()
            assert stats["status"] == "completato" and stats["progress"] == 100
            page.get_by_text("Completato", exact=True).wait_for()
            capture("diagnostics-collaudo-complete.png")
            download("complete", "completato")
            page.set_viewport_size({"width": 390, "height": 844})
            start(1200)
            control("advance", 3)
            diagnostic_view()
            before = control()["get_calls"]
            page.get_by_role("button", name="Interrompi collaudo", exact=True).nth(1).click()
            page.get_by_text("Interrotto", exact=True).wait_for()
            evidence["stop_additional_fixture_reads"] = control()["get_calls"] - before
            page.set_viewport_size({"width": 1440, "height": 1000})
            diagnostic_view()
            capture("diagnostics-collaudo-interrupted.png")
            download("interrupted", "interrotto")
            start()
            control("advance", 2)
            control("storage_failure")
            control("advance", 1)
            diagnostic_view()
            page.get_by_text("Parziale", exact=True).wait_for()
            capture("diagnostics-collaudo-partial.png")
            partial = download("partial", "parziale")
            assert (
                next(c for c in partial["verification_results"] if c["check"] == "persistence")[
                    "result"
                ]
                == "FAIL"
            )

            def ordinary_timestamps():
                response = api.get("/api/states")
                assert response.ok
                return {
                    row["entity_id"]: row["state"]
                    for row in response.json()
                    if row["attributes"]
                    .get("friendly_name", "")
                    .endswith("Ultima acquisizione cloud")
                }

            before = ordinary_timestamps()
            assert before
            control("advance", 1)
            after = ordinary_timestamps()
            assert set(before) == set(after) and before != after
            assert all(value not in ("unknown", "unavailable") for value in after.values())
            evidence["ordinary_sensor_updates_after_session_storage_fault"] = True
            stats = control()
            assert all(call["method"] == "GET" for call in stats["calls"])
            page.clock.set_system_time(datetime.fromisoformat(stats["now"]))
            page.goto(base + "/lovelace/pompa-1")
            page.get_by_text("Acqua calda sanitaria", exact=True).wait_for()
            page.wait_for_timeout(500)
            capture("dashboard-preview.png")
            page.goto(base + "/config/integrations/integration/melcloud_diagnostics")
            page.get_by_role("button", name="Aggiungi hub", exact=True).click()
            page.get_by_role("button", name="Invia", exact=True).wait_for()
            page.get_by_text("Ti aiuteremo a trovare", exact=False).wait_for()
            page.wait_for_timeout(300)
            capture("wizard-preview.png")
            page.get_by_role("button", name="Chiudi", exact=True).click()
            config_menu()
            page.locator("step-flow-menu").get_by_text("Assistenza", exact=False).click()
            page.locator("ha-form").wait_for()
            page.wait_for_timeout(300)
            capture("support-preview.png")
            page.get_by_role("button", name="Chiudi", exact=True).click()
            evidence["browser"] = browser.version
            (DEMO / "capture-results.json").write_text(
                json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
            )
            print("Real HA UI captured with synthetic data; results in ignored demo directory.")
        finally:
            browser.close()
            api.dispose()


if __name__ == "__main__":
    main()
