ALTER TABLE hardware_entity ADD owner_eon_id INTEGER;
ALTER TABLE hardware_entity ADD CONSTRAINT hardware_entity_owner_grn_fk FOREIGN KEY (owner_eon_id) REFERENCES Grn (eon_id);

QUIT;
