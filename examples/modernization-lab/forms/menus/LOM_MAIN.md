# LOM_MAIN — documented, not built as a fixture

`LOM_MAIN` is the one custom menu module referenced by every form's
`MenuModule="LOM_MAIN"` attribute (`CUSTOMERS.xml`, `ORDERS.xml`,
`INVENTORY.xml`, `APPROVALS.xml`). FormsLang has no menu-module parser and
a menu carries no block/item/trigger structure to exercise, so there is no
`LOM_MAIN.xml` fixture — this file documents the structure implied by the
four modules' own navigation buttons (`BT_VIEW_APPROVALS`,
`BT_VIEW_INVENTORY`, `BT_VIEW_CUSTOMER` in `ORDERS.xml`; see LOM-MOD-020,
LOM-MOD-022, LOM-MOD-023) plus the conventional Forms toolbar actions every
module exposes (`BT_FIND`, `BT_EXECUTE`, `BT_NEW` — LOM-MOD-033,
LOM-MOD-024).

## Menu structure

```
LOM_MAIN
├── File
│   ├── New Record        (LOM-MOD-024: CLEAR_FORM(NO_VALIDATE) + CREATE_RECORD)
│   ├── Enter Query        (LOM-MOD-033: ENTER_QUERY)
│   ├── Execute Query       (LOM-MOD-033: EXECUTE_QUERY)
│   ├── Save                (COMMIT_FORM)
│   └── Exit                 (EXIT_FORM)
├── Navigate
│   ├── Customers            (OPEN_FORM CUSTOMERS)
│   ├── Orders                (OPEN_FORM ORDERS)
│   ├── Inventory              (OPEN_FORM INVENTORY)
│   └── Approvals               (OPEN_FORM APPROVALS)
└── Help
    └── About
```

## Modernization notes

Every item under `Navigate` is a plain module-to-module jump with no
business logic — the direct APEX equivalent is the application's global
navigation menu (Desktop or Side navigation), one entry per page group. No
`LOM-MOD-###` case is needed for the menu itself; the interesting
navigation decisions are the in-context, parameterized jumps from inside
`ORDERS.fmb` (LOM-MOD-020, LOM-MOD-022, LOM-MOD-023), not this top-level
menu, since those pass state (an order ID, a customer ID) that a plain
menu item never has to.
