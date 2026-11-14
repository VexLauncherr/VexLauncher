name: Auto Build Setup Wizard & Release

on:
  push:
    branches:
      - main
    paths:
      - 'main.py'

jobs:
  build:
    runs-on: windows-latest
    permissions:
      contents: write

    steps:
    - name: Izvuci kod (Checkout)
      uses: actions/checkout@v4
      with:
        token: ${{ secrets.GITHUB_TOKEN }}

    - name: Postavi Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.10'

    - name: Automatski ažuriraj index.html i detektiraj verziju
      shell: python
      run: |
        import re
        import os

        # Pročitaj main.py i pronađi verziju (npr. v1.2 ili 1.2)
        with open("main.py", "r", encoding="utf-8") as f:
            content = f.read()

        match = re.search(r'"launcherVersion":\s*"([^"]+)"', content)
        if match:
            ver = match.group(1)
        else:
            # Alternativni tražilac ako je verzija zapisana negdje drugdje u kodu
            match_alt = re.search(r'v([0-9]+\.[0-9]+)', content)
            ver = match_alt.group(1) if match_alt else "1.2"

        version_tag = f"v{ver}" if not ver.startswith("v") else ver
        print(f"Automatski detektirana verzija iz main.py: {version_tag}")

        # Otvori index.html i automatski zamijeni i bedž verzije i link za download u letu!
        with open("index.html", "r", encoding="utf-8") as f:
            html = f.read()

        # 1. Zamijeni tekst verzije na bedžu (npr. v1.0 / v1.1 -> nova verzija)
        new_html = re.sub(r'v[0-9]+\.[0-9]+\s+Release Available Now', f'{version_tag} Release Available Now', html)
        
        # 2. Zamijeni i direktne linkove za download u index.html da uvijek gađaju novu verziju!
        new_html = re.sub(r'releases/download/v[0-9]+\.[0-9]+/VexLauncher_Setup\.exe', f'releases/download/{version_tag}/VexLauncher_Setup.exe', new_html)

        with open("index.html", "w", encoding="utf-8") as f:
            f.write(new_html)

        # Spremi verziju u GitHub varijablu da je ostali koraci mogu koristiti
        with open(os.environ['GITHUB_ENV'], 'a') as env_file:
            env_file.write(f"LAUNCHER_VERSION={version_tag}\n")

    - name: Spremi izmjene index.html natrag na GitHub
      run: |
        git config --global user.name "github-actions[bot]"
        git config --global user.email "github-actions[bot]@users.noreply.github.com"
        git remote set-url origin https://x-access-token:${{ secrets.GITHUB_TOKEN }}@github.com/${{ github.repository }}.git
        git add index.html
        git commit -m "Auto-update index.html and version to ${{ env.LAUNCHER_VERSION }}" || echo "No changes to commit"
        git push

    - name: Instaliraj Python biblioteke
      run: |
        python -m pip install --upgrade pip
        pip install customtkinter pywebview requests minecraft-launcher-lib pyinstaller

    - name: Kompajliraj u EXE pomoću PyInstallera
      run: |
        pyinstaller --noconsole --onefile --name "VexLauncher" main.py

    - name: Instaliraj Inno Setup preko Chocolatey
      run: |
        choco install innosetup -y

    - name: Kreiraj Setup Wizard (.exe) pomoću Inno Setup-a
      run: |
        iscc setup.iss

    - name: Obriši stari Release/Tag ako postoji da nema konflikta
      uses: dev-drprasad/delete-tag-and-release@v1.1
      with:
        tag_name: ${{ env.LAUNCHER_VERSION }}
        delete_release: true
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      continue-on-error: true

    - name: Kreiraj Release i učitaj Setup Wizard
      uses: softprops/action-gh-release@v2
      with:
        tag_name: ${{ env.LAUNCHER_VERSION }}
        name: VexLauncher ${{ env.LAUNCHER_VERSION }}
        files: Output/VexLauncher_Setup.exe
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
