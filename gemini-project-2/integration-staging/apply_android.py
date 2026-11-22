from pathlib import Path
import shutil
root = Path(r'D:/My_corseproject')
workspace = root/'gemini-project-2'
stage = workspace/'integration-staging/android-update'
backup = workspace/'integration-staging/android-before-server-auth'
source = root/'app/src/main/java/com/example/courseproject'
for item in stage.iterdir():
    target = root/item.name if item.name == 'gradle.properties' else root/'app/src/main/AndroidManifest.xml' if item.name == 'AndroidManifest.xml' else source/item.name
    relative = target.relative_to(root)
    saved = backup/relative
    saved.parent.mkdir(parents=True, exist_ok=True)
    if not saved.exists():
        shutil.copy2(target, saved)
    shutil.copy2(item, target)
# Remove bundled catalogue; retain a backup outside the Android application.
asset = root/'app/src/main/assets/catalog.json'
if asset.exists():
    saved = backup/'app/src/main/assets/catalog.json'
    saved.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(asset, saved)
    asset.unlink()
print('Android update applied; previous source files backed up at', backup)
# Move unused bundled demo media outside the application package.
for relative in ['app/src/main/res/raw/river_adventure.webm', 'app/src/main/res/raw/beaverhead_river.webm', 'app/src/main/res/drawable-nodpi/poster_adventure.jpg', 'app/src/main/res/drawable-nodpi/poster_river.jpg']:
    asset = root/relative
    if asset.exists():
        saved = backup/relative
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(asset, saved)
        asset.unlink()
