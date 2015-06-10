ALTER TABLE virtual_machine DROP CONSTRAINT virtual_machine_resource_fk;
ALTER TABLE virtual_machine ADD CONSTRAINT virtual_machine_resource_fk FOREIGN KEY (resource_id) REFERENCES "resource" (id);
ALTER TABLE virtual_machine DROP CONSTRAINT virtual_machine_machine_fk;
ALTER TABLE virtual_machine ADD CONSTRAINT virtual_machine_machine_fk FOREIGN KEY (machine_id) REFERENCES machine (machine_id);

QUIT;
