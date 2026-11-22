from pathlib import Path
stage = Path('integration-staging/android-update')
source = Path('D:/My_corseproject/app/src/main/java/com/example/courseproject')
for name in ['MainActivity.kt','RegistrationActivity.kt']:
    p = stage/name
    text = p.read_text(encoding='utf-8').replace('            setSingleLine()', '            setSingleLine()\n            isSaveEnabled = false')
    p.write_text(text, encoding='utf-8')
text = (source/'CatalogueActivity.kt').read_text(encoding='utf-8').replace('        super.onCreate(savedInstanceState)', '''        super.onCreate(savedInstanceState)
        if (!SessionManager.isSignedIn(this)) {
            startActivity(Intent(this, MainActivity::class.java))
            finish()
            return
        }''',1)
(stage/'CatalogueActivity.kt').write_text(text, encoding='utf-8')
