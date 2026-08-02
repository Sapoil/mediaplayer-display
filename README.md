# Media Player Display

Petite application permettant d'avoir un affichage plein écran du média en cours dans le Media Manager de Windows.

## Déploiement

Clonez le repo et utiliser cette commande pour générer l'exécutable :
```pyinstaller --onefile --windowed --add-data "ui.html;." --add-data "style.css;." --add-data "icon.ico;." --icon=icon.ico main.py   ```
L'exécutable se trouvera dans le dossier dist/