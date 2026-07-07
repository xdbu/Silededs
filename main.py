# Copyright (c) 2026 YoannCHVL
# Licensed under the MIT License.
# See the LICENSE file in the project root for license information.
#!/usr/bin/env python3

import csv
import json
import os
import random
import re
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
except ImportError:
    class Fore:
        RED = ''; GREEN = ''; YELLOW = ''; BLUE = ''; MAGENTA = ''; CYAN = ''; WHITE = ''; RESET = ''
    class Style:
        BRIGHT = ''; DIM = ''; NORMAL = ''

import requests
from PIL import Image

try:
    from faker import Faker
except ImportError:
    sys.exit("pip install faker")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
INPUT_DIR = "input"
OUTPUT_DIR = "output"
BIOS_FILE = os.path.join(INPUT_DIR, "bios.txt")
UNSPLASH_FILE = os.path.join(INPUT_DIR, "unsplash.tsv")
VISUALGENOME_FILE = os.path.join(INPUT_DIR, "visualgenome.json")
AVATAR_DIR = os.path.join(OUTPUT_DIR, "avatars")
PROFILES_DIR = os.path.join(OUTPUT_DIR, "profiles")

def ensure_dirs():
    """Create input and output directories if they don't exist."""
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def set_title(title):
    if os.name == 'nt':
        os.system(f'title {title}')
    else:
        sys.stdout.write(f'\x1b]2;{title}\x07')

set_title("France Fake Profile Generator ── YoannCHVL")

EMAIL_DOMAINS = [
    "armyspy.com", "cuvox.de", "dayrep.com", "einrot.com", "fleckens.hu",
    "gustr.com", "jourrapide.com", "superrito.com", "teleworm.us",
]

BANNER = f"""
{Fore.CYAN}{Style.BRIGHT}   ▄████████  ▄█   ▄█          ▄████████ ████████▄     ▄████████ ████████▄    ▄████████ 
  ███    ███ ███  ███         ███    ███ ███   ▀███   ███    ███ ███   ▀███  ███    ███ 
  ███    █▀  ███▌ ███         ███    █▀  ███    ███   ███    █▀  ███    ███  ███    █▀  
  ███        ███▌ ███        ▄███▄▄▄     ███    ███  ▄███▄▄▄     ███    ███  ███        
▀███████████ ███▌ ███       ▀▀███▀▀▀     ███    ███ ▀▀███▀▀▀     ███    ███ ▀███████████ 
         ███ ███  ███         ███    █▄  ███    ███   ███    █▄  ███    ███          ███ 
   ▄█    ███ ███  ███▌    ▄   ███    ███ ███   ▄███   ███    ███ ███   ▄███    ▄█    ███ 
 ▄████████▀  █▀   █████▄▄██   ██████████ ████████▀    ██████████ ████████▀   ▄████████▀  
                ▀                                                                   

{Fore.YELLOW}{Style.BRIGHT}  		     A simple fake french identity generator

{Fore.WHITE}         			Vibecoded by {Fore.LIGHTCYAN_EX}YoannCHVL
"""

_session = None
_session_lock = threading.Lock()

def _get_session():
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                sess = requests.Session()
                adapter = requests.adapters.HTTPAdapter(max_retries=2, pool_connections=20, pool_maxsize=40)
                sess.mount("http://", adapter)
                sess.mount("https://", adapter)
                sess.headers.update({
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
                })
                _session = sess
    return _session

def _slugify(text):
    replacements = {
        "é": "e", "è": "e", "ê": "e", "ë": "e",
        "à": "a", "â": "a", "ä": "a",
        "ù": "u", "û": "u", "ü": "u",
        "ô": "o", "ö": "o",
        "î": "i", "ï": "i",
        "ç": "c",
        "æ": "ae", "œ": "oe",
        "É": "e", "È": "e", "Ê": "e", "Ë": "e",
        "À": "a", "Â": "a", "Ä": "a",
        "Ù": "u", "Û": "u", "Ü": "u",
        "Ô": "o", "Ö": "o",
        "Î": "i", "Ï": "i",
        "Ç": "c",
        "Æ": "ae", "Œ": "oe",
    }
    result = text
    for old, new in replacements.items():
        result = result.replace(old, new)
    result = re.sub(r"[^a-z0-9]", "", result.lower())
    return result

def _extract_department_code(postcode):
    if len(postcode) < 2:
        return "00"
    if postcode.startswith("20") and len(postcode) >= 3:
        code = postcode[:3]
        if code in ("200", "201", "202"):
            return "2a"
        elif code in ("203", "204", "205", "206", "207", "208", "209"):
            return "2b"
    if postcode.startswith("97") and len(postcode) >= 3:
        return postcode[:3]
    return postcode[:2]

def _clean_address(address):
    lines = [l.strip() for l in address.splitlines() if l.strip()]
    if not lines:
        return address.strip()
    if len(lines) >= 2 and re.fullmatch(r"\d+", lines[0]):
        result = f"{lines[0]} {lines[1]}"
    else:
        result = lines[0]
    result = re.sub(r"^(\d+),\s*", r"\1 ", result)
    return result

class ProfileGenerator:
    def __init__(self, unsplash_path, visualgenome_path, bios_list):
        self.fake = Faker("fr_FR")
        self.image_urls = []
        self.bios_list = bios_list

        if not os.path.isfile(unsplash_path):
            raise FileNotFoundError(f"Unsplash metadata file not found: {unsplash_path}")
        if not os.path.isfile(visualgenome_path):
            raise FileNotFoundError(f"Visual Genome metadata file not found: {visualgenome_path}")

        print(f"{Fore.CYAN}[*] Loading URLs from {unsplash_path}...")
        unsplash_count = self._load_unsplash(unsplash_path)
        print(f"    -> {Fore.GREEN}{unsplash_count} URLs loaded from Unsplash")

        print(f"{Fore.CYAN}[*] Loading URLs from {visualgenome_path}...")
        vg_count = self._load_visualgenome(visualgenome_path)
        print(f"    -> {Fore.GREEN}{vg_count} URLs loaded from Visual Genome")

        if not self.image_urls:
            raise ValueError("No image URLs found in either metadata file.")
        random.shuffle(self.image_urls)
        print(f"{Fore.CYAN}[*] Total unique image URLs available: {Fore.GREEN}{len(self.image_urls)}")
        print(f"{Fore.CYAN}[*] Bios loaded: {Fore.GREEN}{len(self.bios_list)}")

    def _load_unsplash(self, path):
        count = 0
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            if "photo_image_url" not in reader.fieldnames:
                raise ValueError(f"TSV missing 'photo_image_url' column.")
            for row in reader:
                url = row.get("photo_image_url", "").strip()
                if url:
                    self.image_urls.append(url)
                    count += 1
        return count

    def _load_visualgenome(self, path):
        count = 0
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("Visual Genome file must contain a JSON array.")
        for item in data:
            if isinstance(item, dict):
                url = item.get("url", "").strip()
                if url:
                    self.image_urls.append(url)
                    count += 1
        return count

    def _generate_email_and_url(self, first_name, last_name, postcode):
        slug_first = _slugify(first_name)
        slug_last = _slugify(last_name)
        dept = _extract_department_code(postcode)
        local_part = f"{slug_first}{slug_last}{dept}"
        domain = random.choice(EMAIL_DOMAINS)
        email = f"{local_part}@{domain}"
        fake_mail_url = f"https://www.fakemailgenerator.com/#/{domain}/{local_part}/"
        return email, fake_mail_url

    @staticmethod
    def _download_and_crop_image(url, output_path):
        TARGET_SIZE = 200
        session = _get_session()
        try:
            resp = session.get(url, timeout=20, stream=True)
            resp.raise_for_status()
            img = Image.open(resp.raw).convert("RGB")
            w, h = img.size
            side = min(w, h)
            left = (w - side) // 2
            top = (h - side) // 2
            img = img.crop((left, top, left + side, top + side))
            img = img.resize((TARGET_SIZE, TARGET_SIZE), Image.LANCZOS)
            img.save(output_path, "JPEG", quality=85, optimize=True)
            return True
        except Exception:
            return False

    @staticmethod
    def _download_single(args):
        (profile_id, url, avatar_dir, first_name, last_name, email, fake_mail_url,
         phone, address, city, postcode, birth_date, bio) = args
        avatar_filename = f"profile_{profile_id}.jpg"
        avatar_path = os.path.join(avatar_dir, avatar_filename)
        if os.path.isfile(avatar_path):
            success = True
        else:
            success = ProfileGenerator._download_and_crop_image(url, avatar_path)
        return (profile_id, avatar_filename if success else "", url if success else "", success)

    def generate_batch(self, count, avatar_dir, max_workers=10):
        os.makedirs(avatar_dir, exist_ok=True)
        start_time = time.time()
        print(f"\n{Fore.CYAN}[*] Generating {count} profiles (max {max_workers} parallel downloads)...")

        profile_args = []
        for i in range(1, count + 1):
            fake = self.fake
            first_name = fake.first_name()
            last_name = fake.last_name()
            phone = f"0{random.randint(1, 9)}{''.join(str(random.randint(0, 9)) for _ in range(8))}"
            raw_address = fake.address()
            clean_address = _clean_address(raw_address)
            city = fake.city()
            postcode = fake.postcode()
            birth_date = fake.date_of_birth(minimum_age=18, maximum_age=70).isoformat()
            email, fake_mail_url = self._generate_email_and_url(first_name, last_name, postcode)
            bio = random.choice(self.bios_list)
            url = random.choice(self.image_urls)
            profile_args.append((i, url, avatar_dir, first_name, last_name, email, fake_mail_url,
                                 phone, clean_address, city, postcode, birth_date, bio))

        results = {}
        completed = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(ProfileGenerator._download_single, args): args[0] for args in profile_args}
            for future in as_completed(futures):
                pid, avatar_fn, avatar_ur, success = future.result()
                results[pid] = (avatar_fn, avatar_ur, success)
                completed += 1
                if count > 1:
                    pct = completed / count * 100
                    bar_len = 40
                    filled = int(bar_len * completed / count)
                    bar = "█" * filled + "─" * (bar_len - filled)
                    elapsed = time.time() - start_time
                    print(f"\r  [{Fore.GREEN}{bar}{Fore.RESET}] {completed}/{count} ({pct:.0f}%) -- {elapsed:.1f}s", end="")

        print()
        profiles = []
        for args in profile_args:
            pid = args[0]
            avatar_fn, avatar_ur, _ = results[pid]
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
                "avatar_url": avatar_ur,
            })

        elapsed = time.time() - start_time
        print(f"{Fore.CYAN}[*] Done. {count} profiles in {elapsed:.2f}s ({count/elapsed:.0f} prof/s)")
        return profiles

    @staticmethod
    def save_csv(profiles, output_path):
        if not profiles:
            return
        fieldnames = list(profiles[0].keys())
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(profiles)
        print(f"{Fore.GREEN}[*] CSV saved   -> {output_path}")

    @staticmethod
    def save_json(profiles, output_path):
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(profiles, f, ensure_ascii=False, indent=2)
        print(f"{Fore.GREEN}[*] JSON saved  -> {output_path}")

def generate_realistic_bios(count):
    subjects = [
        "Vibes décontractées", "Énergie positive", "Curiosité infinie", "Amour des belles choses",
        "Créativité en liberté", "Esprit libre", "Joie de vivre", "Simplicité et authenticité",
        "Passion pour la découverte", "Envie d'ailleurs", "Amoureux des rencontres", "Art de vivre",
        "Légèreté et profondeur", "Vivre pleinement", "Toucher du doigt l'essentiel", "S'émerveiller encore",
        "Goût pour l'aventure", "Sensibilité à fleur de peau", "Amour des instants simples", "Voyageur immobile",
        "Passionné par les histoires", "Habité par la beauté du monde", "Curieux de tout", "Attiré par l'inconnu",
        "Fasciné par les coïncidences", "Amoureux des silences", "En quête de sens", "Porté par l'envie",
        "Habité par la lumière", "Toujours en mouvement"
    ]
    vibes = [
        "un esprit libre et léger", "une bonne humeur contagieuse", "une énergie créative",
        "un regard bienveillant", "une grande curiosité", "un enthousiasme communicatif",
        "une douceur de vivre", "une nature optimiste", "une joie simple", "une profondeur d'âme",
        "une sérénité tranquille", "une fraîcheur d'esprit", "une grande ouverture", "un cœur léger",
        "une humeur stable", "une énergie calme", "une force tranquille", "une authenticité rare",
        "une légèreté d'être", "une passion discrète", "un esprit vif", "une grande bienveillance",
        "une inventivité folle", "une sagesse douce", "une sincérité désarmante", "une humeur égale",
        "une énergie douce", "une joie communicative", "une simplicité vraie", "une profondeur lumineuse"
    ]
    passions = [
        "la créativité", "l'exploration", "les rencontres", "les livres et les idées",
        "les arts visuels", "la musique", "les grands espaces", "les conversations profondes",
        "les instants partagés", "les voyages immobiles", "les images et les mots",
        "les découvertes culinaires", "les cinémas du monde", "les coïncidences",
        "les jeux d'écriture", "les expériences sensorielles", "les projets créatifs",
        "les balades sans but", "les rires et les sourires", "les étoiles et les nuages",
        "les lumières de la ville", "les silences partagés", "les discussions enflammées",
        "les instants de flânerie", "les mélodies du quotidien", "les parfums et les couleurs",
        "les matins calmes", "les soirées entre amis", "les libres pensées", "la beauté du monde"
    ]
    actions = [
        "explorer de nouveaux horizons", "apprendre sans cesse", "partager des émotions",
        "créer des liens", "écouter les histoires", "observer le monde", "s'émerveiller souvent",
        "questionner l'évidence", "se laisser surprendre", "aimer sans compter", "rire aux éclats",
        "s'étonner encore", "accueillir l'imprévu", "cultiver le beau", "aimer profondément",
        "vivre pleinement", "célébrer l'instant", "trouver l'équilibre", "chanter dans la vie",
        "danser avec le vent", "écrire l'instant", "rêver éveillé", "créer du lien",
        "s'émerveiller du rien", "se perdre pour mieux se trouver", "accueillir le changement",
        "voir le bon côté", "savourer chaque pas", "aimer sans mesure", "s'élever doucement"
    ]
    tones = [
        "Tout simplement.", "La vie quoi.", "Sans prise de tête.", "Juste moi.", "C'est comme ça.",
        "Toujours en mouvement.", "Pour le meilleur.", "En toute simplicité.", "Naturellement.",
        "L'essentiel est là.", "C'est le chemin.", "On verra bien.", "C'est une aventure.",
        "Vivre et apprendre.", "Ici et maintenant.", "C'est une question de vibe.", "La vie est belle.",
        "On fait avec.", "Et voilà.", "C'est l'instant.", "Toujours curieux.", "Rien de plus.",
        "Au jour le jour.", "Comme ça.", "Toujours ailleurs.", "Sans chichis.", "C'est ça.",
        "Pour l'essentiel.", "On se laisse porter.", "C'est la vie."
    ]
    short_bios = [
        "Aimer, rire, créer, toujours.", "Une vie simple, des rêves grands.",
        "Ici et maintenant, c'est tout.", "Vivre tout simplement, profondément.",
        "Toujours en quête de belles histoires.", "Le bonheur est dans l'instant.",
        "Créer des liens, c'est tout.", "Rien de plus vrai que l'instant.",
        "Rêver, c'est commencer.", "Toujours apprendre, toujours s'émerveiller.",
        "Juste une personne qui aime les belles choses.",
        "S'étonner encore. S'émerveiller toujours.",
        "Vivre en couleur.", "Être soi, c'est suffisant.",
        "Trouver la beauté partout.", "Écrire sa propre histoire, un jour à la fois.",
        "L'essentiel est invisible.", "Aimer sans conditions.",
        "Créer pour ne pas s'effondrer.",
        "Apprendre est la plus belle des aventures.", "Vivre avec le cœur.",
        "Savourer chaque instant.", "La vie est une aventure quotidienne.",
        "Être présent, pleinement.", "Accueillir la vie comme elle vient.",
        "Avoir foi en la beauté du monde.", "Cultiver l'émerveillement.",
        "Vivre léger, aimer fort.", "Trouver la magie dans le quotidien.",
        "S'ouvrir à l'inattendu.", "Grandir doucement, mais sûrement."
    ]

    bios = set()
    max_attempts = count * 100
    attempts = 0

    while len(bios) < count and attempts < max_attempts:
        if random.random() > 0.25:
            s = random.choice(subjects)
            v = random.choice(vibes)
            p = random.choice(passions)
            a = random.choice(actions)
            t = random.choice(tones)
            r = random.randint(1, 3)
            if r == 1:
                bio = f"{s}, {v}. Passion pour {p} : {a}. {t}"
            elif r == 2:
                bio = f"{s}, {v}. {p}, {a}. {t}"
            else:
                bio = f"{s}. {v} : {p}. {a}. {t}"
        else:
            bio = random.choice(short_bios)
            if random.random() > 0.5:
                bio += " " + random.choice(tones)

        bio = " ".join(bio.split())
        bio = bio.replace(" ,", ",").replace(" .", ".")
        if bio and bio[-1] not in ".!?":
            bio += "."
        if len(bio) > 120:
            cut_point = 120
            for punct in [".", "!", "?", " "]:
                pos = bio.rfind(punct, 0, 120)
                if pos > 100:
                    cut_point = pos + 1
                    break
            bio = bio[:cut_point]
            if bio and bio[-1] not in ".!?":
                bio += "."
        bios.add(bio)
        attempts += 1

    return list(bios)

def bio_menu():
    clear_screen()
    print(BANNER)
    print(f"\n{Fore.CYAN}╔════════════════════════════════════════╗")
    print(f"{Fore.CYAN}║{Fore.YELLOW}      REALISTIC BIO GENERATOR          {Fore.CYAN}║")
    print(f"{Fore.CYAN}╚════════════════════════════════════════╝")
    try:
        count = int(input(f"{Fore.WHITE}Number of bios to generate : {Fore.YELLOW}"))
    except ValueError:
        print(f"{Fore.RED}Please enter a valid number.")
        input(f"{Fore.WHITE}\nPress Enter to return to menu...")
        return
    if count <= 0:
        print(f"{Fore.RED}Must be greater than 0.")
        input(f"{Fore.WHITE}\nPress Enter to return to menu...")
        return

    print(f"{Fore.CYAN}Generating {count} realistic bios...")
    bios = generate_realistic_bios(count)
    with open(BIOS_FILE, "w", encoding="utf-8") as f:
        for b in bios:
            f.write(b + "\n")
    print(f"{Fore.GREEN} {len(bios)} bios saved to {BIOS_FILE}")
    input(f"{Fore.WHITE}\nPress Enter to return to menu...")

def profile_menu():
    clear_screen()
    print(BANNER)
    print(f"\n{Fore.CYAN}╔════════════════════════════════════════╗")
    print(f"{Fore.CYAN}║{Fore.YELLOW}      PROFILE GENERATOR                {Fore.CYAN}║")
    print(f"{Fore.CYAN}╚════════════════════════════════════════╝")

    # Check for required input files
    missing = []
    if not os.path.isfile(BIOS_FILE):
        missing.append(BIOS_FILE)
    if not os.path.isfile(UNSPLASH_FILE):
        missing.append(UNSPLASH_FILE)
    if not os.path.isfile(VISUALGENOME_FILE):
        missing.append(VISUALGENOME_FILE)

    if missing:
        print(f"{Fore.RED}Missing required input files:")
        for m in missing:
            print(f"  - {m}")
        print(f"{Fore.YELLOW}Please place the files in the '{INPUT_DIR}/' folder.")
        input(f"{Fore.WHITE}\nPress Enter to return to menu...")
        return

    try:
        count = int(input(f"{Fore.WHITE}Number of profiles : {Fore.YELLOW}"))
    except ValueError:
        print(f"{Fore.RED}Please enter a valid number.")
        input(f"{Fore.WHITE}\nPress Enter to return to menu...")
        return
    if count <= 0:
        print(f"{Fore.RED}Must be greater than 0.")
        input(f"{Fore.WHITE}\nPress Enter to return to menu...")
        return

    with open(BIOS_FILE, "r", encoding="utf-8") as f:
        bios_list = [line.strip() for line in f if line.strip()]
    if not bios_list:
        print(f"{Fore.RED}{BIOS_FILE} is empty.")
        input(f"{Fore.WHITE}\nPress Enter to return to menu...")
        return

    try:
        gen = ProfileGenerator(UNSPLASH_FILE, VISUALGENOME_FILE, bios_list)
        profiles = gen.generate_batch(count, AVATAR_DIR, max_workers=10)
        os.makedirs(PROFILES_DIR, exist_ok=True)
        gen.save_csv(profiles, os.path.join(PROFILES_DIR, "profiles.csv"))
        gen.save_json(profiles, os.path.join(PROFILES_DIR, "profiles.json"))
        print(f"{Fore.GREEN} {len(profiles)} profiles generated in {PROFILES_DIR}/")
        print(f"{Fore.GREEN} Avatars saved in {AVATAR_DIR}/")
    except Exception as e:
        print(f"{Fore.RED}Error : {e}")
    input(f"{Fore.WHITE}\nPress Enter to return to menu...")

def menu():
    ensure_dirs()
    while True:
        clear_screen()
        print(BANNER)
        print(f"\n{Fore.CYAN}			┌────────────────────────────────────────┐")
        print(f"{Fore.CYAN}			│{Fore.YELLOW} 1. {Fore.WHITE}Generate realistic bios             {Fore.CYAN}│")
        print(f"{Fore.CYAN}			│{Fore.YELLOW} 2. {Fore.WHITE}Generate profiles                   {Fore.CYAN}│")
        print(f"{Fore.CYAN}			│{Fore.YELLOW} 3. {Fore.WHITE}Quit                                {Fore.CYAN}│")
        print(f"{Fore.CYAN}			└────────────────────────────────────────┘")
        choice = input(f"{Fore.WHITE}Choice : {Fore.YELLOW}").strip()

        if choice == "1":
            bio_menu()
        elif choice == "2":
            profile_menu()
        elif choice == "3":
            print(f"{Fore.CYAN}Goodbye.")
            break
        else:
            print(f"{Fore.RED}Invalid choice.")
            time.sleep(1.5)

if __name__ == "__main__":
    menu()