# SiteProof development signing

`siteproof-dev.keystore` is a **development-only** signing identity for the debug application id `com.siteproof.app.dev`.

It exists so repeatedly built field-test APKs can update in place instead of forcing inspectors to uninstall the app between test builds. The key is intentionally not a production secret and must never be used for the production package `com.siteproof.app`, Play App Signing, or any release build.

The debug keystore credentials are declared in `app/build.gradle.kts` and are suitable only for this local/CI development channel.
