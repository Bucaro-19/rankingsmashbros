<?php
// EXAMPLE ONLY. Create /home/<cpanel-user>/private-smash/instagram.local.php, mode 600.
// Never paste a real token in this example, Git, chat, a command argument or a web file.
return [
    'enabled' => false,
    'account_id' => 'REPLACE_WITH_INSTAGRAM_USER_ID',
    'access_token' => 'REPLACE_WITH_A_NEW_LONG_LIVED_TOKEN',
    // Actual UTC issue time of the freshly generated 60-day token, not an old token's setup date.
    'issued_at' => 'YYYY-MM-DDTHH:MM:SSZ',
];
