# 3. Projects

A project has a name, optional description/client label, source roots and a target profile. Names do not authorize filesystem access. Source roots are Forms, Database or Supporting capabilities.

**Recent Projects** stores locators, not a second copy of assessment state. **Open Project** opens an existing descriptor. SQLite remains authoritative; source paths in a descriptor alone grant no permission.

Reopening shows saved analysis without rerunning the engine, then checks source hashes. Keep the saved assessment when sources are stale or missing; use **Refresh Analysis** or **Relink** deliberately. Relinking another tree does not make old decisions current merely because filenames match.

Move the project folder together where practical. Relative sources remain portable; external source roots may need relinking. Back up the entire `.formslang` directory, including managed sessions/artifacts, with the application closed or using a consistent SQLite backup procedure.

Original 1.x sessions remain accessible through **Open Existing Session**. Migration copies and binds legacy state; it must not destroy the original. See [project model](../project-model.md).
