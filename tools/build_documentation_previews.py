"""Render clearly labelled illustrative UI previews, without connecting to Home Assistant.

These are documentation mockups, not screenshots of an installed/tested heat pump.
HTML stays in .tools; only the labelled PNGs are published.
"""

import argparse
import base64
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = """
*{box-sizing:border-box}body{margin:0;background:#0b121d;color:#edf4ff;font:17px 'Segoe UI',Arial,sans-serif}
.top{height:86px;padding:18px 42px;display:flex;align-items:center;gap:15px;border-bottom:1px solid #253142;background:#111b29}
.top img{width:46px;height:46px}.title{font-size:22px;font-weight:650;letter-spacing:-.4px}.sub{font-size:13px;color:#90a4bb;margin-top:4px}
.demo{margin-left:auto;border:1px solid #47586f;border-radius:30px;padding:9px 16px;font-size:12px;font-weight:600;color:#b6c6d8;letter-spacing:.6px}
main{padding:35px 44px}h1{font-size:32px;letter-spacing:-.7px;margin:0 0 9px}h2{font-size:19px;margin:0 0 20px;font-weight:600}p{color:#b5c3d4;line-height:1.65;margin:0 0 22px}
.eyebrow{font-size:12px;letter-spacing:1.5px;color:#51c6e4;font-weight:700;margin-bottom:9px}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}
.panel{background:#142031;border:1px solid #2a384d;border-radius:20px;padding:23px}.section{margin-top:24px}.row{display:flex;align-items:center;justify-content:space-between;gap:18px}
.tile{background:#1b293c;border-radius:14px;padding:18px;margin-top:12px;min-height:88px}.name{color:#bac9dc;font-size:14px;margin-bottom:8px}.value{font-size:27px;font-weight:600;letter-spacing:-.3px}.small{font-size:14px;color:#9eb1c9;line-height:1.6}.pill{display:inline-flex;align-items:center;gap:8px;color:#84deca;background:#153c3b;border-radius:18px;padding:7px 12px;font-size:13px}.dot{width:7px;height:7px;border-radius:50%;background:#71d2bb}.accent{color:#54c9e7}.amber{color:#ffc27c}
.footer{position:absolute;bottom:0;left:0;width:100%;padding:16px 44px;border-top:1px solid #253142;background:#0e1724;color:#93a7bf;font-size:12px}
.center{max-width:780px;margin:20px auto}.steps{display:flex;gap:10px;margin-bottom:25px}.step{padding:9px 13px;border-radius:20px;background:#172436;color:#8ea1b9;font-size:12px}.step.active{color:#71d4ed;background:#133c4e}
.field{border:1px solid #42526b;border-radius:12px;padding:17px 18px;margin:16px 0;background:#111c2b}.fieldlabel{font-size:12px;color:#90a7c2;margin-bottom:8px}.choice{border:1px solid #4ec4e2;border-radius:13px;padding:20px;background:#133447;margin:18px 0}.button{background:#45c4e6;color:#06222c;padding:12px 24px;border-radius:22px;font-size:14px;font-weight:700}.mutedbutton{color:#9ed9e9;font-size:14px}.notice{padding:16px 20px;border-radius:12px;background:#122c37;border-left:3px solid #3eb9d6;color:#bcd7e4;font-size:14px;line-height:1.65}.number{display:inline-flex;align-items:center;justify-content:center;width:33px;height:33px;border-radius:50%;background:#1b3f51;color:#71d5ee;margin-right:13px;font-weight:600}.instruction{display:flex;align-items:center;margin:20px 0;color:#cfdaea}.check{font-size:21px;color:#81d8c7;margin-right:10px}
"""

DASHBOARD = """
<div class="row"><div><div class="eyebrow">PANORAMICA IMPIANTO</div><h1>La tua Ecodan, a colpo d’occhio.</h1><p>Stato, temperature e guasti in un unico posto.</p></div><span class="pill"><i class="dot"></i> Monitoraggio · sola lettura</span></div>
<div class="grid">
<section class="panel"><h2>Stato generale</h2><div class="tile"><div class="name">Errore macchina</div><div class="value" style="color:#84deca">Non segnalato</div></div><div class="tile"><div class="name">Cosa sta facendo</div><div class="value">Riscaldamento</div></div><div class="tile"><div class="name">Collegamento Mitsubishi</div><span class="pill"><i class="dot"></i> Connesso</span></div></section>
<section class="panel"><h2>Acqua calda sanitaria</h2><div class="tile"><div class="name">Temperatura acqua</div><div class="value amber">42,0 °C</div></div><div class="tile"><div class="name">Temperatura desiderata</div><div class="value">45,0 °C</div></div><div class="tile"><div class="name">Zona 1 · ambiente</div><div class="value accent">22,5 °C</div></div></section>
<section class="panel"><h2>Guasti e collegamento</h2><div class="tile"><div class="name">Ultimo guasto registrato</div><div class="value amber">P1 <span class="small">· storico dimostrativo</span></div></div><div class="tile"><div class="name">Disponibilità storico</div><div class="value">Disponibile</div></div><div class="tile"><div class="name">Segnale Wi-Fi</div><div class="value">−60 dBm</div></div></section>
</div><div class="notice section">I dati cloud possono essere ritardati. Un valore non disponibile non significa automaticamente un guasto. Le schede aprono i dettagli: non inviano comandi.</div>
"""
WIZARD = """
<div class="center"><div class="steps"><span class="step">1 · Benvenuto</span><span class="step active">2 · Ricerca</span><span class="step">3 · Pompe</span><span class="step">4 · Riepilogo</span></div>
<section class="panel" style="padding:32px"><div class="eyebrow">CONFIGURAZIONE GUIDATA</div><h1>Un account già pronto da usare.</h1><p>Puoi riutilizzare un account MELCloud Home configurato in HA, oppure accedere con un altro account.</p>
<div class="choice"><div class="fieldlabel">Account trovato · esempio fittizio</div><div class="row"><strong>MELCloud Home: d***@example.com</strong><span class="check">✓</span></div></div>
<div class="field"><div class="fieldlabel">Altra possibilità</div>Accedi con un altro account</div>
<div class="notice">Nessun candidato locale riconosciuto? Puoi continuare: la MAC-597IF-E può non annunciarsi in rete. Le pompe verranno cercate nell’account Mitsubishi.</div>
<p class="small" style="margin:20px 0 25px">Questa procedura non cambia temperature o impostazioni della pompa. Le modifiche manuali resteranno disabilitate.</p>
<div class="row"><span class="mutedbutton">Indietro</span><span class="button">Continua</span></div></section></div>
"""
SUPPORT = """
<div class="center"><section class="panel" style="padding:32px"><div class="eyebrow">ASSISTENZA GUIDATA</div><h1>Il report utile, senza cercare file.</h1><p>Scegli il problema e scarica la diagnostica dal menu dell’integrazione. Non serve usare il terminale.</p>
<div class="field"><div class="fieldlabel">Problema da segnalare</div>Guasti P1 o storico errori</div>
<div class="instruction"><span class="number">1</span><div>Prepara il report dal percorso <strong>Assistenza</strong>.</div></div>
<div class="instruction"><span class="number">2</span><div>Chiudi la procedura e scegli <strong>Scarica diagnostica</strong>.</div></div>
<div class="instruction"><span class="number">3</span><div>Allega il file JSON alla segnalazione, senza modificarlo.</div></div>
<div class="notice" style="margin-top:27px"><strong>Nel report:</strong> versioni software, categoria del problema, stato delle letture, richieste recenti e guasti disponibili. Password e token dell’account sono esclusi.</div>
<p class="small" style="margin:20px 0 25px">La raccolta è di sola lettura. Se servono anche i log dettagliati, la guida spiega come attivarli e scaricarli da HA.</p>
<div class="row"><span class="mutedbutton">Nessuna modifica all’impianto</span><span class="button">Prepara report</span></div></section></div>
"""


def main(render):
    temporary = ROOT / ".tools/docs-preview"
    output = ROOT / "docs/images"
    temporary.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    icon = base64.b64encode(
        (ROOT / "custom_components/melcloud_diagnostics/brand/icon.png").read_bytes()
    ).decode()
    browser = shutil.which("google-chrome") or shutil.which("chromium")
    if not browser:
        windows = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
        browser = str(windows) if windows.is_file() else None
    for name, content in (
        ("dashboard-preview", DASHBOARD),
        ("wizard-preview", WIZARD),
        ("support-preview", SUPPORT),
    ):
        html = f"""<!doctype html><html lang="it"><meta charset="utf-8"><title>Anteprima illustrativa MELCloud Diagnostics</title><style>{CSS}</style><body><header class="top"><img alt="" src="data:image/png;base64,{icon}"><div><div class="title">MELCloud Diagnostics</div><div class="sub">Ecodan · Home Assistant</div></div><span class="demo">ANTEPRIMA ILLUSTRATIVA · DATI FITTIZI</span></header><main>{content}</main><footer class="footer">Schema illustrativo per la documentazione, non screenshot di un impianto. L’aspetto reale dipende da versione, tema e schede di Home Assistant.</footer></body></html>"""
        page = temporary / f"{name}.html"
        page.write_text(html, encoding="utf-8")
        if render:
            if not browser:
                raise RuntimeError("Chrome/Chromium is required to render documentation previews")
            subprocess.run(
                [
                    browser,
                    "--headless",
                    "--disable-gpu",
                    "--hide-scrollbars",
                    "--no-first-run",
                    "--no-default-browser-check",
                    f"--user-data-dir={temporary / 'browser-profile'}",
                    "--window-size=1280,900",
                    "--force-device-scale-factor=1",
                    "--virtual-time-budget=1000",
                    f"--screenshot={output / f'{name}.png'}",
                    page.as_uri(),
                ],
                check=True,
                timeout=45,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        print(f"Prepared {name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render", action="store_true")
    main(parser.parse_args().render)
