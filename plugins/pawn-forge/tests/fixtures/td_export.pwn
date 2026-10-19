// Fixture: raw output in the style of the common TextDraw editors.
//Global Textdraws:

new Text:Textdraw0;
new Text:Textdraw1;

Textdraw0 = TextDrawCreate(500.000000, 100.000000, "SPEEDO");
TextDrawBackgroundColor(Textdraw0, 255);
TextDrawFont(Textdraw0, 2);
TextDrawLetterSize(Textdraw0, 0.300000, 1.200000);
TextDrawColor(Textdraw0, -1);
TextDrawSetOutline(Textdraw0, 1);
TextDrawSetProportional(Textdraw0, 1);
TextDrawUseBox(Textdraw0, 1);
TextDrawBoxColor(Textdraw0, 0x00000088);
TextDrawTextSize(Textdraw0, 600.000000, 0.000000);

Textdraw1 = TextDrawCreate(320.000000, 420.000000, "LD_SPAC:white");
TextDrawFont(Textdraw1, 4);
TextDrawTextSize(Textdraw1, 80.000000, 20.000000);
TextDrawColor(Textdraw1, 0xFF0000FF);
TextDrawSetSelectable(Textdraw1, 1);

//Player TextDraws:

new PlayerText:PlayerTextdraw0[MAX_PLAYERS];
new PlayerText:PlayerTextdraw1[MAX_PLAYERS];

PlayerTextdraw0[playerid] = CreatePlayerTextDraw(playerid, 520.000000, 115.000000, "0 km/h");
PlayerTextDrawBackgroundColor(playerid, PlayerTextdraw0[playerid], 255);
PlayerTextDrawFont(playerid, PlayerTextdraw0[playerid], 3);
PlayerTextDrawLetterSize(playerid, PlayerTextdraw0[playerid], 0.400000, 1.600000);
PlayerTextDrawColor(playerid, PlayerTextdraw0[playerid], -1);
PlayerTextDrawAlignment(playerid, PlayerTextdraw0[playerid], 2);
PlayerTextDrawSetProportional(playerid, PlayerTextdraw0[playerid], 1);

PlayerTextdraw1[playerid] = CreatePlayerTextDraw(playerid, 700.000000, 115.000000, "Fuel");
PlayerTextDrawSetSelectable(playerid, PlayerTextdraw1[playerid], 1);
