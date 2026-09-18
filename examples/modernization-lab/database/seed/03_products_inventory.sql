-- =============================================================================
-- LOM seed data -- products and inventory
-- FACT: product_id values are fixed (not sequence-generated), same rationale
-- as customers.
-- FIXTURE: EAST/GADGET-200 (product 2004) is deliberately seeded with only 2
-- units on hand and 0 reserved -- the insufficient-stock scenario used to
-- exercise LOM_INVENTORY_API.validate_quantity / reserve_quantity and the
-- ORDERS.fmb inline quantity check it duplicates (LOM-MOD-025/026).
-- =============================================================================

insert into lom_products (product_id, product_code, product_name, description, unit_price, active_flag)
values (2001, 'WIDGET-STD', 'Standard Widget', 'General-purpose widget, standard grade.', 25.00, 'Y');

insert into lom_products (product_id, product_code, product_name, description, unit_price, active_flag)
values (2002, 'WIDGET-PRO', 'Professional Widget', 'Heavy-duty widget for commercial use.', 89.50, 'Y');

insert into lom_products (product_id, product_code, product_name, description, unit_price, active_flag)
values (2003, 'GADGET-100', 'Gadget Model 100', 'Entry-level gadget.', 149.99, 'Y');

insert into lom_products (product_id, product_code, product_name, description, unit_price, active_flag)
values (2004, 'GADGET-200', 'Gadget Model 200', 'Mid-range gadget, higher throughput.', 289.00, 'Y');

insert into lom_products (product_id, product_code, product_name, description, unit_price, active_flag)
values (2005, 'PART-SCREW-M4', 'M4 Screw Pack (100ct)', 'Fastener pack, M4 x 12mm.', 4.25, 'Y');

insert into lom_products (product_id, product_code, product_name, description, unit_price, active_flag)
values (2006, 'PART-BRACKET', 'Steel Mounting Bracket', 'Galvanized steel bracket.', 12.75, 'Y');

insert into lom_products (product_id, product_code, product_name, description, unit_price, active_flag)
values (2007, 'TOOL-DRILL', 'Cordless Drill', '18V cordless drill, kit.', 199.00, 'Y');

insert into lom_products (product_id, product_code, product_name, description, unit_price, active_flag)
values (2008, 'TOOL-SAW', 'Circular Saw', '7-1/4in circular saw.', 259.00, 'Y');

-- MAIN warehouse: healthy stock across the board
insert into lom_inventory (product_id, warehouse_code, quantity_on_hand, quantity_reserved, reorder_level) values (2001, 'MAIN', 500, 50, 100);
insert into lom_inventory (product_id, warehouse_code, quantity_on_hand, quantity_reserved, reorder_level) values (2002, 'MAIN', 200, 20, 40);
insert into lom_inventory (product_id, warehouse_code, quantity_on_hand, quantity_reserved, reorder_level) values (2003, 'MAIN', 150, 10, 30);
insert into lom_inventory (product_id, warehouse_code, quantity_on_hand, quantity_reserved, reorder_level) values (2004, 'MAIN', 80, 20, 20);
insert into lom_inventory (product_id, warehouse_code, quantity_on_hand, quantity_reserved, reorder_level) values (2005, 'MAIN', 5000, 500, 500);
insert into lom_inventory (product_id, warehouse_code, quantity_on_hand, quantity_reserved, reorder_level) values (2006, 'MAIN', 1000, 100, 150);
insert into lom_inventory (product_id, warehouse_code, quantity_on_hand, quantity_reserved, reorder_level) values (2007, 'MAIN', 60, 20, 15);
insert into lom_inventory (product_id, warehouse_code, quantity_on_hand, quantity_reserved, reorder_level) values (2008, 'MAIN', 40, 10, 10);

-- EAST warehouse: smaller stock; 2004 is the intentional low-stock case
insert into lom_inventory (product_id, warehouse_code, quantity_on_hand, quantity_reserved, reorder_level) values (2001, 'EAST', 100, 10, 25);
insert into lom_inventory (product_id, warehouse_code, quantity_on_hand, quantity_reserved, reorder_level) values (2002, 'EAST', 40, 5, 10);
insert into lom_inventory (product_id, warehouse_code, quantity_on_hand, quantity_reserved, reorder_level) values (2003, 'EAST', 30, 5, 10);
insert into lom_inventory (product_id, warehouse_code, quantity_on_hand, quantity_reserved, reorder_level) values (2004, 'EAST', 2, 0, 15);
insert into lom_inventory (product_id, warehouse_code, quantity_on_hand, quantity_reserved, reorder_level) values (2005, 'EAST', 800, 100, 150);
insert into lom_inventory (product_id, warehouse_code, quantity_on_hand, quantity_reserved, reorder_level) values (2006, 'EAST', 150, 20, 40);
insert into lom_inventory (product_id, warehouse_code, quantity_on_hand, quantity_reserved, reorder_level) values (2007, 'EAST', 15, 5, 10);
insert into lom_inventory (product_id, warehouse_code, quantity_on_hand, quantity_reserved, reorder_level) values (2008, 'EAST', 10, 5, 8);

commit;
