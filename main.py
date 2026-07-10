#!/usr/bin/env python3
# Copyright (c) 2026 YoannCHVL
# Licensed under the MIT License.

import csv
import json
import os
import random
import re
import sys
import time
import shutil
import threading
import gzip
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.theme import Theme
    from rich.text import Text
    from rich import box
    from rich.align import Align
    custom_theme = Theme({
        "info": "bold cyan",
        "success": "bold green",
        "warning": "bold yellow",
        "error": "bold red",
        "accent": "bold magenta",
        "banner": "bold bright_cyan",
        "muted": "dim white"
    })
    console = Console(theme=custom_theme)
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

try:
    from flask import Flask, render_template_string, request, jsonify, send_from_directory
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False

try:
    from faker import Faker
except ImportError:
    sys.exit("pip install faker")

import requests
from PIL import Image

INPUT_DIR = "input"
OUTPUT_DIR = "output"
BAN_DIR = os.path.join(INPUT_DIR, "ban_compressed")
UNSPLASH_FILE = os.path.join(INPUT_DIR, "unsplash.tsv")
VISUALGENOME_FILE = os.path.join(INPUT_DIR, "visualgenome.json")
VILLES_FILE = os.path.join(INPUT_DIR, "villes_france.json")
AVATAR_DIR = os.path.join(OUTPUT_DIR, "avatars")
PROFILES_DIR = os.path.join(OUTPUT_DIR, "profiles")

EMAIL_DOMAINS = ["armyspy.com", "cuvox.de", "dayrep.com", "einrot.com", "fleckens.hu", "gustr.com", "jourrapide.com", "superrito.com", "teleworm.us"]

BANNER_TEXT = """
    ▄████████  ▄█   ▄█           ▄████████ ████████▄       ▄████████ ████████▄    ▄████████ 
   ███    ███ ███  ███          ███    ███ ███    ▀███     ███    ███ ███    ▀███  ███    ███ 
   ███    █▀  ███▌ ███          ███    █▀  ███     ███     ███    █▀  ███     ███  ███    █▀  
   ███        ███▌ ███         ▄███▄▄▄     ███     ███   ▄███▄▄▄      ███     ███  ███        
 ▀███████████ ███▌ ███        ▀▀███▀▀▀     ███     ███  ▀▀███▀▀▀      ███     ███ ▀███████████ 
          ███ ███  ███          ███    █▄  ███     ███     ███    █▄  ███     ███          ███ 
    ▄█    ███ ███  ███▌    ▄    ███    ███ ███    ▄███     ███    ███ ███    ▄███    ▄█    ███ 
  ▄████████▀  █▀   █████▄▄██    ██████████ ████████▀       ██████████ ████████▀    ▄████████▀  
"""

def ensure_dirs():
    for d in [INPUT_DIR, BAN_DIR, OUTPUT_DIR, AVATAR_DIR, PROFILES_DIR]:
        os.makedirs(d, exist_ok=True)

def clear_output_directory():
    if os.path.exists(AVATAR_DIR):
        shutil.rmtree(AVATAR_DIR)
    os.makedirs(AVATAR_DIR, exist_ok=True)
    for fn in ["profiles.csv", "profiles.json"]:
        p = os.path.join(PROFILES_DIR, fn)
        if os.path.exists(p):
            os.remove(p)

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    if HAS_RICH:
        banner_text = Text(BANNER_TEXT, style="banner")
        subtitle = Text("\n       A premium fake french identity generator & ecosystem\n", style="warning")
        credits = Text("       Vibecoded by ", style="muted")
        credits.append("YoannCHVL", style="accent")
        full_banner = Text.assemble(banner_text, subtitle, credits)
        console.print(Panel(Align.center(full_banner), border_style="cyan", padding=(1, 2), width=console.width))
    else:
        print(BANNER_TEXT)

def log_info(msg): console.print(f"[info][*][/info] {msg}") if HAS_RICH else print(f"[*] {msg}")
def log_success(msg): console.print(f"[success][✓][/success] {msg}") if HAS_RICH else print(f"[✓] {msg}")
def log_error(msg): console.print(f"[error][✕][/error] {msg}") if HAS_RICH else print(f"[✕] {msg}")

_session = None
_session_lock = threading.Lock()

def _get_session():
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                sess = requests.Session()
                adapter = requests.adapters.HTTPAdapter(max_retries=2, pool_connections=50, pool_maxsize=100)
                sess.mount("http://", adapter)
                sess.mount("https://", adapter)
                sess.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"})
                _session = sess
    return _session

def _slugify(text):
    replacements = {"é": "e", "è": "e", "ê": "e", "ë": "e", "à": "a", "â": "a", "ä": "a", "ù": "u", "û": "u", "ü": "u", "ô": "o", "ö": "o", "î": "i", "ï": "i", "ç": "c", "æ": "ae", "œ": "oe", "É": "e", "È": "e", "Ê": "e", "Ë": "e", "À": "a", "Â": "a", "Ä": "a", "Ù": "u", "Û": "u", "Ü": "u", "Ô": "o", "Ö": "o", "Î": "i", "Ï": "i", "Ç": "c"}
    result = text
    for old, new in replacements.items():
        result = result.replace(old, new)
    return re.sub(r"[^a-z0-9]", "", result.lower())

def _extract_department_code(postcode):
    if len(postcode) < 2:
        return "00"
    if postcode.startswith("20"):
        if postcode.startswith("200") or postcode.startswith("201"):
            return "2A"
        return "2B"
    return postcode[:2]

class ProfileGenerator:
    def __init__(self, unsplash_path, visualgenome_path, villes_path, bios_list):
        self.fake = Faker("fr_FR")
        self.image_urls = []
        self.villes_data = []
        self.bios_list = bios_list
        self._load_datasets(unsplash_path, visualgenome_path, villes_path)

    def _load_datasets(self, unsplash_path, visualgenome_path, villes_path):
        if os.path.isfile(villes_path):
            with open(villes_path, "r", encoding="utf-8") as f:
                self.villes_data = json.load(f)
        else:
            self.villes_data = [{"city": "Paris", "postcode": "75001"}]

        if os.path.isfile(unsplash_path):
            with open(unsplash_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter="\t")
                if "photo_image_url" in reader.fieldnames:
                    self.image_urls.extend([row["photo_image_url"].strip() for row in reader if row.get("photo_image_url")])
        if os.path.isfile(visualgenome_path):
            with open(visualgenome_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    self.image_urls.extend([item["url"].strip() for item in data if isinstance(item, dict) and item.get("url")])
        if not self.image_urls:
            self.image_urls = [f"https://picsum.photos/800/800?random={i}" for i in range(100)]
        random.shuffle(self.image_urls)

    def _get_random_address_data_from_ban(self, postcode, city_name):
        dept = _extract_department_code(postcode)
        gz_path = os.path.join(BAN_DIR, f"adresses-{dept}.csv.gz")
        if not os.path.exists(gz_path):
            return None
        matching_rows = []
        target_city_slug = _slugify(city_name)
        try:
            with gzip.open(gz_path, mode="rt", encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter=";")
                for row in reader:
                    if _slugify(row.get("nom_commune", "")) == target_city_slug:
                        matching_rows.append(row)
                        if len(matching_rows) >= 150:
                            break
        except:
            return None
        if matching_rows:
            chosen = random.choice(matching_rows)
            street_num = chosen.get("numero", "")
            rep = chosen.get("rep", "")
            street_name = chosen.get("nom_voie", "")
            full_street = f"{street_num} {rep}".strip() + f" {street_name}"
            return {
                "address": full_street.strip(),
                "city": chosen.get("nom_commune", city_name),
                "postal_code": chosen.get("code_postal", postcode)
            }
        return None

    def generate_batch(self, count, avatar_dir, max_workers=25, silent=False):
        clear_output_directory()
        os.makedirs(avatar_dir, exist_ok=True)
        profile_args = []
        for i in range(1, count + 1):
            first_name = self.fake.first_name()
            last_name = self.fake.last_name()
            phone = f"0{random.randint(1, 9)}{''.join(str(random.randint(0, 9)) for _ in range(8))}"
            location = random.choice(self.villes_data)
            initial_city = location["city"]
            initial_postcode = location["postcode"]
            ban_data = self._get_random_address_data_from_ban(initial_postcode, initial_city)
            if ban_data:
                real_street = ban_data["address"]
                final_city = ban_data["city"]
                final_postcode = ban_data["postal_code"]
            else:
                real_street = f"{random.randint(1, 199)} {self.fake.street_name()}"
                final_city = initial_city
                final_postcode = initial_postcode
            chosen_domain = random.choice(EMAIL_DOMAINS)
            email_user = f"{_slugify(first_name)}{_slugify(last_name)}{_extract_department_code(final_postcode)}"
            email = f"{email_user}@{chosen_domain}"
            fake_mail_url = f"https://www.fakemailgenerator.com/#/{chosen_domain}/{email_user}/"
            bio = self.bios_list[i-1] if i-1 < len(self.bios_list) else "Passionné de nouvelles technologies."
            avatar_filename = f"profile_{i}_{_slugify(first_name)}_{_slugify(last_name)}.jpg"
            profile_args.append((
                i,
                random.choice(self.image_urls) if self.image_urls else "",
                avatar_dir,
                first_name,
                last_name,
                email,
                fake_mail_url,
                phone,
                real_street,
                final_city,
                final_postcode,
                self.fake.date_of_birth(minimum_age=18, maximum_age=70).isoformat(),
                bio,
                avatar_filename
            ))

        results = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self._download_single, args): args[0] for args in profile_args}
            for future in as_completed(futures):
                pid, final_fn, final_url = future.result()
                results[pid] = (final_fn, final_url)

        profiles = []
        for args in profile_args:
            pid = args[0]
            avatar_fn, avatar_url = results[pid]
            profiles.append({
                "id": pid,
                "first_name": args[3],
                "last_name": args[4],
                "email": args[5],
                "fake_mail_url": args[6],
                "phone": args[7],
                "birth_date": args[11],
                "address": args[8],
                "city": args[9],
                "postal_code": args[10],
                "bio": args[12],
                "avatar_filename": avatar_fn,
                "avatar_url": avatar_url
            })
        return profiles

    @staticmethod
    def _download_single(args):
        (profile_id, initial_url, avatar_dir, first_name, last_name, email, fake_mail_url, phone, address, city, postcode, birth_date, bio, avatar_filename) = args
        avatar_path = os.path.join(avatar_dir, avatar_filename)
        success = False
        url_used = initial_url
        if initial_url and "unsplash.com" in initial_url and "w=" not in initial_url:
            if "?" in initial_url:
                initial_url += "&auto=format&fit=crop&w=800&h=800&q=95"
            else:
                initial_url += "?auto=format&fit=crop&w=800&h=800&q=95"
            url_used = initial_url
        if initial_url:
            success = ProfileGenerator._download_and_crop_image(initial_url, avatar_path)
        if not success:
            fallback_url = f"https://picsum.photos/800/800?random={profile_id}"
            success = ProfileGenerator._download_and_crop_image(fallback_url, avatar_path)
            url_used = fallback_url if success else ""
        return (profile_id, avatar_filename if success else "", url_used)

    @staticmethod
    def _download_and_crop_image(url, output_path):
        try:
            resp = _get_session().get(url, timeout=12, stream=True)
            resp.raise_for_status()
            img = Image.open(resp.raw).convert("RGB")
            w, h = img.size
            side = min(w, h)
            left = (w - side) // 2
            top = (h - side) // 2
            right = left + side
            bottom = top + side
            img = img.crop((left, top, right, bottom))
            img = img.resize((400, 400), Image.Resampling.LANCZOS)
            img.save(output_path, "JPEG", quality=95, optimize=True)
            return True
        except:
            return False

    @staticmethod
    def save_csv(profiles, output_path):
        if not profiles:
            return
        fieldnames = list(profiles[0].keys())
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(profiles)

    @staticmethod
    def save_json(profiles, output_path):
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(profiles, f, ensure_ascii=False, indent=2)

def generate_realistic_bios(count):
    fk = Faker("fr_FR")
    passions = ["le gardening", "la photographie de rue", "la cuisine", "les randonnées", "la programmation", "la lecture", "les jeux vidéo", "le modélisme", "les voyages", "la peinture", "le cinéma"]
    traits = ["Curieux de tout et optimiste", "Esprit calme et créatif", "Toujours en quête d'aventures", "Passionné par le partage", "Amoureux de la nature", "Esprit analytique, mordu de tech"]
    bios = []
    for _ in range(count):
        job = fk.job().lower()
        structures = [
            f"{random.choice(traits)}. Exerce en tant que {job} et adore {random.choice(passions)}.",
            f"{job.capitalize()} passionné par {random.choice(passions)}. {random.choice(traits)}.",
            f"{random.choice(traits)}, investi dans {random.choice(passions)}. Travaille comme {job}."
        ]
        bios.append(random.choice(structures))
    return bios

def run_cli_generation():
    clear_screen()
    print_banner()
    console.print(Panel(Align.center("CONSTRUIRE DES IDENTITÉS"), border_style="cyan", expand=False))
    try:
        console.print("[info]>[/info] Quantité désirée : ", end="")
        count = int(input())
    except ValueError:
        log_error("Entrée invalide.")
        time.sleep(1.5)
        return
    log_info("Instanciation du moteur & analyse BAN locale...")
    bios = generate_realistic_bios(count)
    gen = ProfileGenerator(UNSPLASH_FILE, VISUALGENOME_FILE, VILLES_FILE, bios)
    profiles = gen.generate_batch(count, AVATAR_DIR, max_workers=25)
    ProfileGenerator.save_csv(profiles, os.path.join(PROFILES_DIR, "profiles.csv"))
    ProfileGenerator.save_json(profiles, os.path.join(PROFILES_DIR, "profiles.json"))
    table = Table(title="Derniers Profils Générés (Aperçu)", border_style="cyan", box=box.ROUNDED, width=min(console.width, 100))
    table.add_column("ID", style="dim", width=6)
    table.add_column("Nom Complet", style="bold white", width=20)
    table.add_column("Adresse Réelle", style="accent", width=30)
    table.add_column("Code Postal & Ville", style="success", width=25)
    for p in profiles[:5]:
        table.add_row(str(p["id"]), f"{p['first_name']} {p['last_name']}", p["address"][:30], f"{p['postal_code']} {p['city']}")
    console.print("\n", table)
    input("\n[Appuyez sur Entrée pour revenir au menu]")

app = Flask(__name__)

WEB_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fake Profile Generator Suite</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen font-sans">
    <nav class="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-50 px-6 py-4 flex justify-between items-center">
        <div class="flex items-center space-x-3">
            <div class="bg-cyan-500 text-slate-900 p-2 rounded-lg font-bold"><i class="fa-solid fa-id-card"></i></div>
            <span class="text-xl font-extrabold tracking-wider bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">FR-IDENTITY GEN</span>
        </div>
        <div class="text-xs text-slate-500 font-mono">By YoannCHVL © 2026</div>
    </nav>
    <main class="max-w-7xl mx-auto p-6 space-y-10">
        <section class="bg-slate-800/50 border border-slate-700/60 rounded-2xl p-6 backdrop-blur shadow-xl">
            <h2 class="text-lg font-semibold text-cyan-400 mb-4 flex items-center gap-2"><i class="fa-solid fa-sliders"></i> Tableau de Configuration</h2>
            <div class="flex flex-col md:flex-row gap-4 items-end">
                <div class="flex-1">
                    <label class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">Nombre de Profils à Générer</label>
                    <input type="number" id="countInput" value="6" min="1" max="100" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 focus:outline-none focus:border-cyan-500 text-slate-100 font-mono transition">
                </div>
                <button onclick="generateProfiles()" id="genBtn" class="bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-900 font-bold px-8 py-3 rounded-xl transition shadow-lg shadow-cyan-500/10 flex items-center gap-2 whitespace-nowrap">
                    <i class="fa-solid fa-bolt"></i> Générer Instantanément
                </button>
            </div>
        </section>
        <div id="loader" class="hidden text-center py-12">
            <div class="inline-block animate-spin rounded-full h-12 w-12 border-4 border-cyan-500 border-t-transparent mb-4"></div>
            <p class="text-slate-400 text-sm animate-pulse">Création des identités, lecture locale des .csv.gz et traitement des avatars...</p>
        </div>
        <div class="bg-blue-950/40 border border-blue-800/50 rounded-xl p-4 flex items-center gap-3 text-sm text-blue-300 shadow-md">
            <i class="fa-solid fa-circle-info text-blue-400 text-base"></i>
            <span>Chaque génération effectuée met à jour et sauvegarde automatiquement les fichiers structurés ainsi que les images dans le répertoire local <span class="bg-slate-950 px-2 py-0.5 rounded font-mono text-cyan-400 border border-slate-800">output/</span>.</span>
        </div>
        <section>
            <div class="flex justify-between items-center mb-6">
                <h2 class="text-xl font-bold tracking-tight text-white flex items-center gap-2"><i class="fa-solid fa-users"></i> Profils Actuels</h2>
                <div class="flex gap-2">
                    <a href="/download/csv" class="text-xs bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 px-3 py-2 rounded-lg transition flex items-center gap-1"><i class="fa-solid fa-file-csv text-green-500"></i> CSV</a>
                    <a href="/download/json" class="text-xs bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 px-3 py-2 rounded-lg transition flex items-center gap-1"><i class="fa-solid fa-file-code text-yellow-500"></i> JSON</a>
                </div>
            </div>
            <div id="profilesGrid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            </div>
        </section>
    </main>
    {% raw %}
    <script>
        async function generateProfiles() {
            const count = document.getElementById('countInput').value;
            const btn = document.getElementById('genBtn');
            const loader = document.getElementById('loader');
            btn.disabled = true;
            loader.classList.remove('hidden');
            try {
                const response = await fetch(`/api/generate?count=${count}`);
                const data = await response.json();
                renderProfiles(data);
            } catch (err) {
                alert('Erreur lors de la génération.');
            } finally {
                btn.disabled = false;
                loader.classList.add('hidden');
            }
        }
        function renderProfiles(profiles) {
            const grid = document.getElementById('profilesGrid');
            grid.innerHTML = '';
            if(!profiles || profiles.length === 0) {
                grid.innerHTML = '<div class="col-span-full text-center text-slate-500 py-12">Aucun profil chargé. Appuyez sur générer !</div>';
                return;
            }
            profiles.forEach(p => {
                const card = `
                    <div class="bg-slate-800/30 border border-slate-700/40 rounded-2xl overflow-hidden hover:border-cyan-500/40 transition duration-300 flex flex-col justify-between group shadow-lg">
                        <div class="p-6 space-y-4">
                            <div class="flex items-center space-x-4">
                                <img src="/avatars/${p.avatar_filename}" onerror="this.src='https://picsum.photos/400'" class="w-16 h-16 rounded-full object-cover border-2 border-cyan-500/30 group-hover:border-cyan-400 transition">
                                <div>
                                    <h3 class="text-lg font-bold text-white">${p.first_name} ${p.last_name}</h3>
                                    <p class="text-xs text-cyan-400 font-mono">${p.birth_date}</p>
                                </div>
                            </div>
                            <p class="text-slate-400 text-sm italic">"${p.bio}"</p>
                            <div class="border-t border-slate-700/40 pt-4 space-y-2 text-xs font-mono text-slate-300">
                                <div class="flex items-center gap-2"><i class="fa-solid fa-envelope text-slate-500 w-4"></i> ${p.email}</div>
                                <div class="flex items-center gap-2"><i class="fa-solid fa-phone text-slate-500 w-4"></i> ${p.phone}</div>
                                <div class="flex items-center gap-2"><i class="fa-solid fa-location-dot text-slate-500 w-4"></i> ${p.address}, ${p.postal_code} ${p.city}</div>
                            </div>
                        </div>
                        <div class="bg-slate-950/40 px-6 py-3 border-t border-slate-700/30 text-right">
                            <a href="${p.fake_mail_url}" target="_blank" class="text-xs text-cyan-400 hover:underline inline-flex items-center gap-1">Boite Mail Active <i class="fa-solid fa-arrow-up-right-from-square text-[10px]"></i></a>
                        </div>
                    </div>
                `;
                grid.insertAdjacentHTML('beforeend', card);
            });
        }
        fetch('/api/current').then(res => res.json()).then(data => renderProfiles(data));
    </script>
    {% endraw %}
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(WEB_TEMPLATE)

@app.route('/api/generate')
def api_generate():
    count = request.args.get('count', default=6, type=int)
    gen = ProfileGenerator(UNSPLASH_FILE, VISUALGENOME_FILE, VILLES_FILE, generate_realistic_bios(count))
    profiles = gen.generate_batch(count, AVATAR_DIR, max_workers=25, silent=True)
    ProfileGenerator.save_csv(profiles, os.path.join(PROFILES_DIR, "profiles.csv"))
    ProfileGenerator.save_json(profiles, os.path.join(PROFILES_DIR, "profiles.json"))
    return jsonify(profiles)

@app.route('/api/current')
def api_current():
    path = os.path.join(PROFILES_DIR, "profiles.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return jsonify(json.load(f))
    return jsonify([])

@app.route('/avatars/<filename>')
def serve_avatar(filename):
    return send_from_directory(AVATAR_DIR, filename)

@app.route('/download/<file_type>')
def download_file(file_type):
    return send_from_directory(PROFILES_DIR, f"profiles.{file_type}", as_attachment=True)

def run_web_server():
    clear_screen()
    print_banner()
    if not HAS_FLASK:
        sys.exit("pip install flask")
    console.print(Panel("[success]SERVEUR ECOSYSTEME INTERFACE WEB LANCÉ ![/success]\n\nOuvrez votre navigateur sur : [bold underline cyan]http://127.0.0.1:5000[/bold underline cyan]"))
    app.run(port=5000, debug=False, use_reloader=False)

def menu():
    ensure_dirs()
    while True:
        clear_screen()
        print_banner()
        if HAS_RICH:
            console.print(Panel(Align.center(" [info]1.[/info] Lancer la génération (CLI)\n [info]2.[/info] Interface Web (Flask)\n [info]3.[/info] Quitter"), title="[warning]SÉLECTION[/warning]", border_style="cyan", expand=False))
            choice = input("> ").strip()
        else:
            choice = input("1. CLI / 2. Web / 3. Quitter\n> ").strip()
        if choice == "1":
            run_cli_generation()
        elif choice == "2":
            run_web_server()
        elif choice == "3":
            break

if __name__ == "__main__":
    menu()