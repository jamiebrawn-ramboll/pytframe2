import datetime
import os
import re
import shutil
import time
import urllib.parse
import zipfile

import arcpy
from arcpy import Parameter

import utils.archelp as archelp
from utils.archelp import Parameters, print
from utils.tool import Tool


class A5SurveyProcessor(Tool):
    def __init__(self):
        """Define the tool (tool name is the class name)."""
        super().__init__()

        self.category = "Processing"
        self.label = "A5 Survey Processor"
        self.alias = self.label.replace(" ", "")
        self.description = (
            "Process survey data from portal or file geodatabase, adds fields, calculates geometry and performs spatial joins"
        )
        self.canRunInBackground = False
        return

    def getParameterInfo(self) -> list[Parameter]:
        """Define parameter definitions"""

        # Parameter 0: Survey Dataset (browsable)
        param0 = arcpy.Parameter(
            displayName="Survey Dataset",
            name="survey_input",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input",
        )
        param0.value = "https://gis-eu.ramboll.com/arcgis/rest/services/Hosted/A5WTCS2_BatPRASurvey01/FeatureServer/0"

        # Parameter 1: Red Line Boundary (browsable)
        param1 = arcpy.Parameter(
            displayName="Red Line Boundary",
            name="rlb_input",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input",
        )
        param1.value = "https://gis-eu.ramboll.com/arcgis/rest/services/Hosted/A5WTCS2_RAM_GN_ZZ_C_RedLineBoundarySection2P08_Py_01/FeatureServer/0"

        # Parameter 2: Zone (browsable)
        param2 = arcpy.Parameter(
            displayName="Zone",
            name="zone_input",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input",
        )
        param2.value = "https://gis-eu.ramboll.com/arcgis/rest/services/Hosted/A5WTCS2_RAM_GN_ZZ_C_Zones_Py_02/FeatureServer/0"

        # Parameter 3: Land Ownership Parcel (browsable)
        param3 = arcpy.Parameter(
            displayName="Land Ownership Parcel",
            name="ownership_input",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input",
        )
        param3.value = "https://gis-eu.ramboll.com/arcgis/rest/services/Hosted/A5WTCS2_WSP_LO_ZZ_C_LandOwnershipSurveyAccess30mBuffer_Py_06/FeatureServer/0"

        # Parameter 4: Output Location
        param4 = arcpy.Parameter(
            displayName="Output Location",
            name="output_location",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input",
        )
        # Set default to project's default folder
        try:
            # Try to get the project's default geodatabase folder
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            if aprx.defaultGeodatabase:
                param4.value = os.path.dirname(aprx.defaultGeodatabase)
            else:
                param4.value = arcpy.env.workspace or os.getcwd()
        except:
            param4.value = os.getcwd()

        # Parameter 5: Output Geodatabase Name
        param5 = arcpy.Parameter(
            displayName="Output Geodatabase Name",
            name="output_gdb_name",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
        )

        # Parameter 6: Output Feature Class Name
        param6 = arcpy.Parameter(
            displayName="Output Feature Class Name",
            name="output_fc_name",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
        )

        # HIDDEN PARAMETERS FOR STATE TRACKING
        # Parameter 7: Track the last input value we processed
        param7 = arcpy.Parameter(
            displayName="Last Input Value (Hidden)",
            name="last_input_value",
            datatype="GPString",
            parameterType="Optional",
            direction="Input",
            category="Advanced",  # This puts it in a collapsible section
        )
        param7.enabled = False  # Make it read-only to users

        # Parameter 8: Track whether we've done initial setup
        param8 = arcpy.Parameter(
            displayName="Initial Setup Done (Hidden)",
            name="initial_setup_done",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
            category="Advanced",
        )
        param8.enabled = False
        param8.value = False

        return [
            param0,  # survey_input
            param1,  # rlb_input
            param2,  # zone_input
            param3,  # ownership_input
            param4,  # output_location
            param5,  # output_gdb_name
            param6,  # output_fc_name
            param7,  # last_input_value (hidden)
            param8,  # initial_setup_done (hidden)
        ]

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""

        try:
            # Get current input value as string for comparison
            current_input_str = str(parameters[0].value) if parameters[0].value else ""

            # Get last processed input value from hidden parameter
            last_input_str = str(parameters[7].value) if parameters[7].value else ""

            # Check if we've done initial setup
            initial_setup_done = (
                parameters[8].value if parameters[8].value is not None else False
            )

            # Determine if we should update the output names:
            # 1. Input has actually changed (different from last processed), OR
            # 2. We haven't done initial setup yet AND we have a valid input
            should_update_names = (
                current_input_str != last_input_str and current_input_str != ""
            ) or (not initial_setup_done and current_input_str != "")

            if should_update_names:
                # Extract meaningful name from input
                input_name = self._get_portal_item_name(parameters[0].value)

                # Generate new suggested names using the enhanced pattern logic
                if input_name and input_name != "Unknown":
                    # Apply the A5WTCS2 pattern logic
                    pattern_name = self._generate_a5wtcs2_pattern(input_name)
                    new_gdb_name = f"{pattern_name}_ProcessedSurvey"
                    new_fc_name = f"{input_name}_Processed"
                else:
                    new_gdb_name = "A5WTCS2_RAM_ES_ZZ_G_ProcessedSurvey"
                    new_fc_name = "ProcessedSurvey"

                # Update the visible output parameters
                parameters[5].value = new_gdb_name
                parameters[6].value = new_fc_name

                # Update the hidden tracking parameters
                parameters[7].value = current_input_str  # Remember this input value
                parameters[8].value = True  # Mark initial setup as done

                # Log for debugging
                arcpy.AddMessage(f"Updated output names based on input: {input_name}")
                arcpy.AddMessage(f"Applied pattern: {pattern_name}")

        except Exception as e:
            # If any error occurs, set fallback names only if we were supposed to update
            arcpy.AddMessage(f"Error in updateParameters: {str(e)}")

            try:
                if should_update_names:  # Only update if we were supposed to
                    parameters[5].value = "A5WTCS2_RAM_ES_ZZ_G_ProcessedSurvey"
                    parameters[6].value = "ProcessedSurvey"
                    parameters[7].value = current_input_str
                    parameters[8].value = True
            except:
                pass  # If even the fallback fails, just continue

        return

    def _generate_a5wtcs2_pattern(self, input_name):
        """Generate A5WTCS2 naming pattern with intelligent prefix logic.

        Pattern: A5WTCS2_{XXX}_{XX}_{XX}_{X}_
        Defaults: A5WTCS2_RAM_ES_ZZ_G_

        Args:
            input_name: The extracted input name

        Returns:
            String with proper A5WTCS2 pattern applied
        """
        if not input_name or input_name == "Unknown":
            return "A5WTCS2_RAM_ES_ZZ_G"

        # Default pattern parts
        defaults = ["RAM", "ES", "ZZ", "G"]
        expected_lengths = [3, 2, 2, 1]  # XXX_XX_XX_X

        # If doesn't start with A5WTCS2, add full default prefix
        if not input_name.upper().startswith("A5WTCS2"):
            return f"A5WTCS2_RAM_ES_ZZ_G_{input_name}"

        # Remove A5WTCS2_ prefix and split remaining parts
        remaining = input_name[8:] if len(input_name) > 8 else ""  # Remove "A5WTCS2_"
        parts = remaining.split("_") if remaining else []

        # Try to match parts to expected positions
        matched_parts = []
        part_index = 0

        for pos, expected_length in enumerate(expected_lengths):
            if part_index < len(parts):
                current_part = parts[part_index]
                # Check if current part matches expected length and is alphabetic
                if (
                    len(current_part) == expected_length
                    and current_part.replace("_", "").isalpha()
                ):
                    matched_parts.append(current_part.upper())
                    part_index += 1
                else:
                    # Use default for this position and stop matching
                    matched_parts.extend(defaults[pos:])
                    break
            else:
                # No more parts, use defaults for remaining positions
                matched_parts.extend(defaults[pos:])
                break

        # Construct the base result
        result = "A5WTCS2_" + "_".join(matched_parts)

        # Any remaining unmatched parts get appended
        if part_index < len(parts):
            remaining_parts = parts[part_index:]
            result += "_" + "_".join(remaining_parts)

        return result

    def _get_portal_item_name(self, input_value):
        """Helper method to extract meaningful name from any layer type."""
        if not input_value:
            return "Unknown"

        try:
            # First, try to get the layer name - this often works for map layers
            layer_name = None
            if hasattr(input_value, "name"):
                layer_name = str(input_value.name)
                if (
                    layer_name
                    and not layer_name.isdigit()
                    and layer_name.lower() != "unknown"
                ):
                    clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", layer_name)
                    if clean_name and clean_name != "_":
                        arcpy.AddMessage(f"Using layer name: {clean_name}")
                        return clean_name

            # Get the data source path
            data_source = None
            if hasattr(input_value, "dataSource"):
                data_source = str(input_value.dataSource)
            else:
                data_source = str(input_value)

            arcpy.AddMessage(f"Processing data source: {data_source}")

            # Extract name based on data source type
            extracted_name = None

            # 1. Portal/Server URLs
            if "/rest/services/" in data_source:
                match = re.search(
                    r"/services/(?:[^/]+/)?([^/]+)/(?:FeatureServer|MapServer)",
                    data_source,
                )
                if match:
                    extracted_name = match.group(1)

            # 2. File Geodatabase paths
            elif ".gdb" in data_source.lower():
                # Match pattern: path/to/data.gdb/FeatureClassName
                gdb_match = re.search(
                    r"\.gdb[/\\]([^/\\]+)$", data_source, re.IGNORECASE
                )
                if gdb_match:
                    extracted_name = gdb_match.group(1)
                else:
                    # Fallback: get last component after gdb
                    parts = re.split(r"[/\\]", data_source)
                    if len(parts) > 1:
                        extracted_name = parts[-1]

            # 3. Shapefile paths
            elif ".shp" in data_source.lower():
                shp_name = os.path.basename(data_source)
                extracted_name = re.sub(r"\.shp$", "", shp_name, flags=re.IGNORECASE)

            # 4. Other file paths
            elif os.path.sep in data_source or "/" in data_source:
                base_name = os.path.basename(data_source)
                if base_name:
                    # Remove common file extensions
                    extracted_name = re.sub(
                        r"\.(shp|gdb|mdb|accdb|dbf|tab|kml|kmz|gpx)$",
                        "",
                        base_name,
                        flags=re.IGNORECASE,
                    )

            # 5. Database connections (look for dot notation)
            elif "." in data_source:
                parts = data_source.split(".")
                if len(parts) >= 2:
                    extracted_name = parts[
                        -1
                    ]  # Use the last part (likely feature class name)

            # Clean and validate the extracted name
            if extracted_name:
                clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", extracted_name)
                if clean_name and clean_name != "_" and not clean_name.isdigit():
                    arcpy.AddMessage(f"Extracted name: {clean_name}")
                    return clean_name

            # Final fallback: try layer name again if we haven't used it
            if layer_name and layer_name != "Unknown":
                clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", layer_name)
                if clean_name and clean_name != "_":
                    arcpy.AddMessage(f"Using layer name as fallback: {clean_name}")
                    return clean_name

            arcpy.AddMessage("Could not extract meaningful name, using 'Unknown'")
            return "Unknown"

        except Exception as e:
            arcpy.AddMessage(f"Error extracting name: {str(e)}")
            # Simple fallback attempt
            try:
                if hasattr(input_value, "name"):
                    simple_name = re.sub(r"[^a-zA-Z0-9_]", "_", str(input_value.name))
                    if simple_name and simple_name != "_":
                        return simple_name
            except:
                pass
            return "Unknown"

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def _cleanup_workspace(self, gdb_path=None):
        """Clean up workspace locks and temporary data more aggressively"""
        try:
            # Clear workspace cache
            arcpy.ClearWorkspaceCache_management()

            # Reset environment variables
            arcpy.env.workspace = ""

            if gdb_path and arcpy.Exists(gdb_path):
                try:
                    # Attempt to clear any orphaned edit sessions
                    temp_edit = arcpy.da.Editor(gdb_path)
                    if temp_edit.isEditing:
                        temp_edit.stopEditing(False)  # Discard any unsaved edits
                except:
                    pass  # Ignore if no edit session exists

                try:
                    # Compact the geodatabase to remove fragmentation and versioning artifacts
                    arcpy.management.Compact(gdb_path)
                except:
                    pass  # Ignore if compact fails

                # Add a delay to allow file handles to release
                time.sleep(3)

            # Delete any in_memory layers
            arcpy.Delete_management("in_memory") if arcpy.Exists("in_memory") else None

            # Force garbage collection to release any lingering references
            import gc

            gc.collect()

        except Exception as e:
            arcpy.AddWarning(f"Warning during workspace cleanup: {str(e)}")

    def _validate_objectid_integrity(self, feature_class):
        """Validate ObjectID integrity - check for duplicates and gaps"""
        try:
            arcpy.AddMessage("Validating ObjectID integrity...")

            # Get all ObjectIDs
            oid_list = []
            with arcpy.da.SearchCursor(feature_class, ["OBJECTID"]) as cursor:
                for row in cursor:
                    oid_list.append(row[0])

            # Check for duplicates
            unique_oids = set(oid_list)
            if len(oid_list) != len(unique_oids):
                arcpy.AddError(
                    f"CRITICAL: Duplicate ObjectIDs found! Total: {len(oid_list)}, Unique: {len(unique_oids)}"
                )
                return False

            # Check for reasonable sequence (no major gaps)
            if oid_list:
                min_oid = min(oid_list)
                max_oid = max(oid_list)
                expected_range = max_oid - min_oid + 1
                actual_count = len(oid_list)

                if (
                    expected_range > actual_count * 2
                ):  # Allow for some gaps but not excessive
                    arcpy.AddMessage(
                        f"Large gaps in ObjectID sequence detected. Range: {expected_range}, Count: {actual_count}"
                    )

            arcpy.AddMessage(
                f"ObjectID validation passed. Count: {len(oid_list)}, Range: {min_oid}-{max_oid}"
            )
            return True

        except Exception as e:
            arcpy.AddError(f"Error validating ObjectID integrity: {str(e)}")
            return False

    def _get_best_spatial_matches(
        self, target_fc, join_fc, target_geom_type, join_value_field
    ):
        """Get best spatial matches based on geometry type"""
        try:
            best_matches = {}

            if target_geom_type == "Point":
                # For points: find closest polygon centroid
                arcpy.AddMessage("Using centroid distance method for point features...")

                with arcpy.da.SearchCursor(
                    join_fc, ["TARGET_FID", join_value_field, "SHAPE@", "Join_Count"]
                ) as cursor:
                    for row in cursor:
                        target_oid = row[0]
                        join_value = row[1]
                        join_polygon = row[2]
                        join_count = row[3] if row[3] is not None else 0

                        if (
                            join_value and join_polygon and join_count > 0
                        ):  # Only consider actual intersections
                            # Get polygon centroid
                            centroid = (
                                join_polygon.centroid
                                if join_polygon.centroid
                                else join_polygon.labelPoint
                            )

                            # Get target point geometry
                            target_point = None
                            with arcpy.da.SearchCursor(
                                target_fc, ["OBJECTID", "SHAPE@"]
                            ) as target_cursor:
                                for target_row in target_cursor:
                                    if target_row[0] == target_oid:
                                        target_point = target_row[1]
                                        break

                            if target_point and centroid:
                                # Calculate distance from point to polygon centroid
                                distance = target_point.distanceTo(centroid)

                                # Keep closest centroid
                                if (
                                    target_oid not in best_matches
                                    or distance < best_matches[target_oid][1]
                                ):
                                    best_matches[target_oid] = (join_value, distance)

            else:
                # For lines/polygons: find largest overlap area
                arcpy.AddMessage(
                    f"Using overlap area method for {target_geom_type.lower()} features..."
                )

                with arcpy.da.SearchCursor(
                    join_fc, ["TARGET_FID", join_value_field, "SHAPE@", "Join_Count"]
                ) as cursor:
                    for row in cursor:
                        target_oid = row[0]
                        join_value = row[1]
                        join_geom = row[2]
                        join_count = row[3] if row[3] is not None else 0

                        if join_value and join_geom and join_count > 0:
                            # Get target geometry
                            target_geom = None
                            with arcpy.da.SearchCursor(
                                target_fc, ["OBJECTID", "SHAPE@"]
                            ) as target_cursor:
                                for target_row in target_cursor:
                                    if target_row[0] == target_oid:
                                        target_geom = target_row[1]
                                        break

                            if target_geom:
                                # Calculate overlap area/length
                                try:
                                    intersection = target_geom.intersect(
                                        join_geom, 4
                                    )  # Dimension 4 for area/length
                                    if intersection:
                                        if target_geom_type == "Polygon":
                                            overlap_measure = intersection.area
                                        else:  # Polyline
                                            overlap_measure = intersection.length

                                        # Keep largest overlap
                                        if (
                                            target_oid not in best_matches
                                            or overlap_measure
                                            > best_matches[target_oid][1]
                                        ):
                                            best_matches[target_oid] = (
                                                join_value,
                                                overlap_measure,
                                            )
                                except:
                                    # Fallback to join count if geometry operations fail
                                    if (
                                        target_oid not in best_matches
                                        or join_count > best_matches[target_oid][1]
                                    ):
                                        best_matches[target_oid] = (
                                            join_value,
                                            join_count,
                                        )

            return best_matches

        except Exception as e:
            arcpy.AddError(f"Error calculating best spatial matches: {str(e)}")
            return {}

    def _safe_remove_directory(self, directory_path):
        """Safely remove a directory with retry logic"""
        if not os.path.exists(directory_path):
            return True

        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # Force close any open files
                self._cleanup_workspace()
                time.sleep(2)  # Wait for resources to be released

                # Remove directory
                shutil.rmtree(directory_path, ignore_errors=True)

                # Verify removal
                time.sleep(1)
                if not os.path.exists(directory_path):
                    return True

                arcpy.AddMessage(f"Removal attempt {attempt+1} incomplete, retrying...")
                time.sleep(3)  # Longer wait between attempts

            except Exception as e:
                arcpy.AddWarning(f"Removal attempt {attempt+1} failed: {str(e)}")
                time.sleep(3)  # Wait before retry

        arcpy.AddWarning(f"Could not fully remove directory: {directory_path}")

        return False

    def _rename_related_files(self, gdb_path, old_fc_name, new_fc_name):
        """Rename related files like __ATTACH and __ATTACHREL tables and relationship classes"""
        try:
            arcpy.AddMessage(
                f"Checking for related files to rename from {old_fc_name} to {new_fc_name}..."
            )

            # Store original workspace
            original_workspace = arcpy.env.workspace
            arcpy.env.workspace = gdb_path

            # Get all tables and feature classes
            all_tables = arcpy.ListTables() or []
            all_fcs = arcpy.ListFeatureClasses() or []
            all_datasets = all_tables + all_fcs

            # Also get relationship classes
            all_relationships = []
            try:
                all_relationships = (
                    arcpy.ListDatasets(dataset_type="Relationship") or []
                )
            except:
                # Fallback method if ListDatasets doesn't work
                try:
                    desc = arcpy.Describe(gdb_path)
                    if hasattr(desc, "children"):
                        for child in desc.children:
                            if (
                                hasattr(child, "dataType")
                                and child.dataType == "RelationshipClass"
                            ):
                                all_relationships.append(child.name)
                except:
                    pass

            # Combine all geodatabase objects
            all_objects = all_datasets + all_relationships

            # Debug: List all objects to see what's there
            arcpy.AddMessage(f"All tables/FCs in GDB: {all_datasets}")
            arcpy.AddMessage(f"All relationship classes in GDB: {all_relationships}")

            # Find related files that start with old_fc_name followed by "__"
            related_files = []
            for obj_name in all_objects:
                if obj_name.startswith(f"{old_fc_name}__"):
                    related_files.append(obj_name)

            if related_files:
                arcpy.AddMessage(
                    f"Found {len(related_files)} related files to rename: {related_files}"
                )

                # Force cleanup before renaming
                self._cleanup_workspace(gdb_path)
                time.sleep(1)

                # Rename each related file/relationship class
                for old_name in related_files:
                    try:
                        suffix = old_name[
                            len(old_fc_name) :
                        ]  # Get the "__ATTACH" or "__ATTACHREL" part
                        new_name = f"{new_fc_name}{suffix}"

                        old_path = os.path.join(gdb_path, old_name)
                        arcpy.AddMessage(
                            f"Attempting to rename: {old_name} -> {new_name}"
                        )

                        if arcpy.Exists(old_path):
                            arcpy.management.Rename(old_path, new_name)
                            arcpy.AddMessage(
                                f"Successfully renamed: {old_name} -> {new_name}"
                            )
                        else:
                            arcpy.AddWarning(f"Related object not found: {old_path}")
                    except Exception as e:
                        arcpy.AddWarning(f"Failed to rename {old_name}: {str(e)}")
            else:
                arcpy.AddMessage("No related files found to rename")

        except Exception as e:
            arcpy.AddWarning(f"Warning during related file rename: {str(e)}")
        finally:
            # Restore original workspace
            arcpy.env.workspace = original_workspace

    # Consolidated Edit Session for All Field Updates
    def _update_fields_with_single_edit(
        self,
        source_gdb,
        source_fc,
        zone_matches,
        ownership_matches,
        ownership_field_name,
    ):
        """Update all fields in a single edit session to minimize versioning issues"""
        arcpy.AddMessage(
            "Updating zone and ownership values with a single edit session..."
        )

        # Clear any potential lingering locks before edit
        self._cleanup_workspace(source_gdb)
        time.sleep(2)  # Wait for locks to clear

        edit = arcpy.da.Editor(source_gdb)
        updates_made = 0

        try:
            # Start edit session with explicit undo/redo stack disabled
            edit.startEditing(False, False)
            edit.startOperation()

            # Update both fields in a single cursor
            with arcpy.da.UpdateCursor(
                source_fc, ["OBJECTID", "zone", ownership_field_name]
            ) as cursor:
                for row in cursor:
                    oid = row[0]
                    modified = False

                    # Update zone if we have a match
                    if oid in zone_matches:
                        row[1] = zone_matches[oid]
                        modified = True

                    # Update ownership if we have a match
                    if oid in ownership_matches:
                        row[2] = str(ownership_matches[oid][0])
                        modified = True

                    # Only update the row if we changed something
                    if modified:
                        cursor.updateRow(row)
                        updates_made += 1

            # Commit changes
            edit.stopOperation()
            edit.stopEditing(True)
            arcpy.AddMessage(f"Total rows updated: {updates_made}")

            return True

        except Exception as e:
            # Cancel operation on error
            arcpy.AddError(f"Error during edit session: {str(e)}")
            try:
                edit.stopOperation()
            except:
                pass
            try:
                edit.stopEditing(False)
            except:
                pass
            return False
        finally:
            # Ensure workspace is cleaned up
            time.sleep(2)  # Wait for edit session to fully close
            self._cleanup_workspace(source_gdb)

    def execute(self, parameters, messages):
        """The source code of the tool."""
        temp_layer = None

        try:
            # Get parameter values
            survey_input = parameters[0].value
            rlb_input = parameters[1].value
            zone_input = parameters[2].value
            ownership_input = parameters[3].value
            output_location = parameters[4].valueAsText
            output_gdb_name = parameters[5].valueAsText
            output_fc_name = parameters[6].valueAsText

            # Create unique timestamp for file naming
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            arcpy.AddMessage(f"Using timestamp for unique file naming: {timestamp}")

            # Step 1: Package the input data with ObjectID preservation
            arcpy.AddMessage("Step 1: Packaging input layer to preserve ObjectIDs...")

            # Clear all environment variables
            arcpy.ResetEnvironments()

            # Reset all geoprocessing environments
            arcpy.env.workspace = ""
            arcpy.env.scratchWorkspace = ""
            arcpy.env.overwriteOutput = True

            # Force release workspace locks
            arcpy.ClearWorkspaceCache_management()

            # Force Python garbage collection multiple times
            import gc

            gc.collect()
            time.sleep(1)
            gc.collect()

            # Delete in_memory workspace entirely
            arcpy.Delete_management("in_memory") if arcpy.Exists("in_memory") else None

            # Create and immediately delete a temporary geodatabase
            # This can force ArcGIS to refresh its internal registry
            temp_gdb = os.path.join(
                arcpy.env.scratchFolder, f"temp_reset_{timestamp}.gdb"
            )
            if arcpy.Exists(temp_gdb):
                arcpy.Delete_management(temp_gdb)
            arcpy.CreateFileGDB_management(
                arcpy.env.scratchFolder, f"temp_reset_{timestamp}.gdb"
            )
            time.sleep(2)
            arcpy.Delete_management(temp_gdb)

            # Create temporary layer with proper cleanup tracking
            temp_layer = "in_memory_survey"
            arcpy.management.MakeFeatureLayer(survey_input, temp_layer)

            # Package to .lpkx (preserves ObjectIDs) - using output_gdb_name with timestamp
            lpkx_path = os.path.join(
                arcpy.env.scratchFolder, f"{output_gdb_name}_{timestamp}.lpkx"
            )
            arcpy.management.PackageLayer(
                in_layer=temp_layer, output_file=lpkx_path, convert_data="CONVERT"
            )

            # Extract the package - using shorter names to avoid Windows path length limits
            extract_dir = os.path.join(arcpy.env.scratchFolder, f"pkg_orig_{timestamp}")
            arcpy.management.ExtractPackage(
                in_package=lpkx_path, output_folder=extract_dir
            )
            arcpy.AddMessage(f"Original package extracted to: {extract_dir}")

            # Step 2: Create a complete duplicate of the _pkg folder for processing
            arcpy.AddMessage(
                "Step 2: Creating duplicate package folder for processing..."
            )
            duplicate_dir = os.path.join(
                arcpy.env.scratchFolder, f"pkg_dup_{timestamp}"
            )

            # Clean duplicate directory if it exists
            if os.path.exists(duplicate_dir):
                shutil.rmtree(duplicate_dir, ignore_errors=True)
                time.sleep(0.5)

            # Copy entire package structure
            shutil.copytree(extract_dir, duplicate_dir)
            arcpy.AddMessage(f"Duplicate package created at: {duplicate_dir}")

            # Step 3: Work on the DUPLICATE package
            # Locate the extracted geodatabase in the duplicate
            commondata_dir = os.path.join(duplicate_dir, "commondata")
            source_gdb = os.path.join(commondata_dir, "featureserver.gdb")

            if not arcpy.Exists(source_gdb):
                raise arcpy.ExecuteError(f"Expected GDB not found at {source_gdb}")

            # Set workspace to the duplicate GDB for processing
            original_workspace = arcpy.env.workspace
            arcpy.env.workspace = source_gdb

            # Find the main feature class (exclude attachment tables)
            all_fcs = arcpy.ListFeatureClasses()
            candidate_fcs = [
                fc
                for fc in all_fcs
                if not (fc.endswith("__ATTACH") or fc.endswith("__ATTACHREL"))
            ]

            if not candidate_fcs:
                raise arcpy.ExecuteError(
                    f"No valid feature class found in {source_gdb}"
                )

            source_fc = os.path.join(source_gdb, candidate_fcs[0])
            arcpy.AddMessage(
                f"Processing feature class: {candidate_fcs[0]} in duplicate package"
            )

            # Step 4: Validate initial ObjectID integrity on DUPLICATE
            if not self._validate_objectid_integrity(source_fc):
                raise arcpy.ExecuteError(
                    "Initial ObjectID validation failed on duplicate"
                )

            # Step 5: Add fields while in duplicate commondata (preserves ObjectIDs)
            arcpy.AddMessage("Step 3: Adding fields in duplicate commondata...")

            # Note: Keep the date for field names (as per user requirement)
            current_date = datetime.datetime.now().strftime("%d%m%y")
            x_field_name = f"x_{current_date}"
            y_field_name = f"y_{current_date}"
            x_field_alias = f"X_{current_date}"
            y_field_alias = f"Y_{current_date}"
            ownership_field_name = "landownershipparcel"
            ownership_field_alias = "LandOwnershipParcel"

            # Add coordinate fields
            arcpy.management.AddField(
                source_fc, x_field_name, "DOUBLE", field_alias=x_field_alias
            )
            arcpy.management.AddField(
                source_fc, y_field_name, "DOUBLE", field_alias=y_field_alias
            )
            arcpy.management.AddField(
                source_fc, "zone", "TEXT", field_length=50, field_alias="Zone"
            )
            arcpy.management.AddField(
                source_fc,
                ownership_field_name,
                "TEXT",
                field_length=100,
                field_alias=ownership_field_alias,
            )

            # Step 6: Calculate geometry attributes
            arcpy.AddMessage("Step 4: Calculating geometry attributes...")

            desc = arcpy.Describe(source_fc)
            geom_type = desc.shapeType

            irish_grid_sr = "PROJCS['TM65_Irish_Grid',GEOGCS['GCS_TM65',DATUM['D_TM65',SPHEROID['Airy_Modified',6377340.189,299.3249646]],PRIMEM['Greenwich',0.0],UNIT['Degree',0.0174532925199433]],PROJECTION['Transverse_Mercator'],PARAMETER['False_Easting',200000.0],PARAMETER['False_Northing',250000.0],PARAMETER['Central_Meridian',-8.0],PARAMETER['Scale_Factor',1.000035],PARAMETER['Latitude_Of_Origin',53.5],UNIT['Meter',1.0]];-5123200 -14700000 10000;-100000 10000;-100000 10000;0.001;0.001;0.001;IsHighPrecision"

            if geom_type == "Point":
                geometry_props = [[x_field_name, "POINT_X"], [y_field_name, "POINT_Y"]]
            elif geom_type == "Polyline":
                geometry_props = [
                    [x_field_name, "LINE_START_X"],
                    [y_field_name, "LINE_START_Y"],
                ]
            elif geom_type == "Polygon":
                geometry_props = [
                    [x_field_name, "CENTROID_X"],
                    [y_field_name, "CENTROID_Y"],
                ]

            arcpy.management.CalculateGeometryAttributes(
                in_features=source_fc,
                geometry_property=geometry_props,
                coordinate_system=irish_grid_sr,
            )

            # Step 7: Near analysis (preserves ObjectIDs)
            arcpy.AddMessage("Step 5: Running Near analysis...")
            arcpy.analysis.Near(
                in_features=source_fc,
                near_features=rlb_input,
                search_radius="",
                location="NO_LOCATION",
                angle="NO_ANGLE",
                method="PLANAR",
            )

            # Step 8: Process Zone data with geometry-specific best matches
            arcpy.AddMessage(
                "Step 6: Processing Zone data with geometry-specific best matches..."
            )

            zone_join_fc = os.path.join(source_gdb, "Zone_Join_Temp")

            # Create field mappings to ensure we get the zone field with consistent naming
            field_mappings = arcpy.FieldMappings()
            field_mappings.addTable(source_fc)

            zone_field_map = arcpy.FieldMap()
            zone_field_map.addInputField(zone_input, "zone")
            output_field = zone_field_map.outputField
            output_field.name = "temp_zone_value"
            output_field.aliasName = "Temporary Zone Value"
            zone_field_map.outputField = output_field
            field_mappings.addFieldMap(zone_field_map)

            # Perform spatial join for ZONE
            arcpy.analysis.SpatialJoin(
                target_features=source_fc,
                join_features=zone_input,
                out_feature_class=zone_join_fc,
                join_operation="JOIN_ONE_TO_ONE",
                join_type="KEEP_ALL",
                field_mapping=field_mappings,
                match_option="INTERSECT",
            )

            # Get best matches using geometry-specific method for ZONE
            best_zone_matches = self._get_best_spatial_matches(
                target_fc=source_fc,
                join_fc=zone_join_fc,
                target_geom_type=geom_type,
                join_value_field="temp_zone_value",
            )

            # Process zone values (extract last 2 characters)
            processed_zone_matches = {}
            for oid, (zone_value, metric) in best_zone_matches.items():
                if zone_value:
                    zone_str = str(zone_value).strip()
                    extracted_zone = zone_str[-2:] if len(zone_str) >= 2 else zone_str
                    processed_zone_matches[oid] = extracted_zone

            # Step 9: Process Land Ownership with geometry-specific best matches
            arcpy.AddMessage(
                "Step 7: Processing Land Ownership with geometry-specific best matches..."
            )

            ownership_join_fc = os.path.join(source_gdb, "Ownership_Join_Temp")

            # Create field mappings for OWNERSHIP
            field_mappings = arcpy.FieldMappings()
            field_mappings.addTable(source_fc)

            ownership_field_map = arcpy.FieldMap()
            ownership_field_map.addInputField(ownership_input, "parnumtxt")
            output_field = ownership_field_map.outputField
            output_field.name = "temp_ownership_value"
            output_field.aliasName = "Temporary Ownership Value"
            ownership_field_map.outputField = output_field
            field_mappings.addFieldMap(ownership_field_map)

            # Perform spatial join for OWNERSHIP
            arcpy.analysis.SpatialJoin(
                target_features=source_fc,
                join_features=ownership_input,
                out_feature_class=ownership_join_fc,
                join_operation="JOIN_ONE_TO_ONE",
                join_type="KEEP_ALL",
                field_mapping=field_mappings,
                match_option="INTERSECT",
            )

            # Get best matches using geometry-specific method for OWNERSHIP
            best_ownership_matches = self._get_best_spatial_matches(
                target_fc=source_fc,
                join_fc=ownership_join_fc,
                target_geom_type=geom_type,
                join_value_field="temp_ownership_value",
            )

            # NOW use the consolidated edit session to update BOTH fields at once
            update_success = self._update_fields_with_single_edit(
                source_gdb,
                source_fc,
                processed_zone_matches,
                best_ownership_matches,
                ownership_field_name,
            )

            if not update_success:
                raise arcpy.ExecuteError("Failed to update fields in the feature class")

            # Clean up temporary joins
            arcpy.management.Delete(zone_join_fc)
            arcpy.management.Delete(ownership_join_fc)

            # Step 10: Final ObjectID validation before copying
            arcpy.AddMessage(
                "Step 8: Final ObjectID validation on processed duplicate..."
            )
            if not self._validate_objectid_integrity(source_fc):
                raise arcpy.ExecuteError(
                    "Final ObjectID validation failed on processed duplicate"
                )

            arcpy.env.workspace = original_workspace
            self._cleanup_workspace(source_gdb)

            # Give system time to release all locks
            time.sleep(3)

            # Step 11: Create final output locations
            arcpy.AddMessage("Step 9: Preparing final output locations...")
            final_pkg_dir = os.path.join(
                output_location, f"{output_gdb_name}_pkg_final_{timestamp}"
            )
            final_gdb_for_convenience = os.path.join(
                output_location, f"{output_gdb_name}.gdb"
            )

            # Step 12: Safely remove existing directories if they exist
            self._safe_remove_directory(final_pkg_dir)
            self._safe_remove_directory(final_gdb_for_convenience)

            # Step 13: Copy the processed package with retry logic
            arcpy.AddMessage(
                "Step 10: Copying processed package to final location with retry logic..."
            )
            max_copy_attempts = 3
            copy_success = False

            for attempt in range(max_copy_attempts):
                try:
                    # Force cleanup before copy attempt
                    self._cleanup_workspace()
                    time.sleep(1)

                    # Copy the entire processed package structure
                    shutil.copytree(duplicate_dir, final_pkg_dir)
                    arcpy.AddMessage(f"Processed package copied to: {final_pkg_dir}")
                    copy_success = True
                    break
                except Exception as e:
                    arcpy.AddWarning(f"Copy attempt {attempt+1} failed: {str(e)}")
                    time.sleep(3)  # Wait before retry

            if not copy_success:
                raise arcpy.ExecuteError(
                    "Failed to copy processed package to final location"
                )

            # Step 14: Create the convenience GDB with retry logic
            arcpy.AddMessage(
                "Step 11: Creating convenience geodatabase with retry logic..."
            )
            final_gdb_source = os.path.join(
                final_pkg_dir, "commondata", "featureserver.gdb"
            )
            copy_success = False

            for attempt in range(max_copy_attempts):
                try:
                    # Force cleanup before copy attempt
                    self._cleanup_workspace()
                    time.sleep(1)

                    # Copy just the GDB for easy access
                    shutil.copytree(final_gdb_source, final_gdb_for_convenience)
                    arcpy.AddMessage(
                        f"Convenience GDB created at: {final_gdb_for_convenience}"
                    )
                    copy_success = True
                    break
                except Exception as e:
                    arcpy.AddWarning(
                        f"Convenience GDB creation attempt {attempt+1} failed: {str(e)}"
                    )
                    time.sleep(3)  # Wait before retry

            if not copy_success:
                arcpy.AddWarning(
                    "Failed to create convenience GDB. Package folder still available."
                )
                # Continue instead of failing - the package folder is more important

            # Step 15: Rename feature class and related files in convenience GDB
            if (
                copy_success
                and candidate_fcs[0] != output_fc_name
                and arcpy.Exists(final_gdb_for_convenience)
            ):
                arcpy.AddMessage(
                    "Step 12: Renaming feature class and related files in convenience GDB..."
                )
                try:
                    old_fc_path = os.path.join(
                        final_gdb_for_convenience, candidate_fcs[0]
                    )
                    if arcpy.Exists(old_fc_path):
                        # Force any cleanup before rename
                        self._cleanup_workspace(final_gdb_for_convenience)
                        time.sleep(1)

                        # Rename related files first (before renaming main FC)
                        self._rename_related_files(
                            final_gdb_for_convenience, candidate_fcs[0], output_fc_name
                        )

                        # Then rename the main feature class
                        arcpy.management.Rename(old_fc_path, output_fc_name)
                        arcpy.AddMessage(f"Feature class renamed to: {output_fc_name}")

                except Exception as e:
                    arcpy.AddWarning(f"Warning during feature class rename: {str(e)}")
                    # Continue instead of failing - the data is still usable

            # Step 16: Final processing and validation on convenience GDB
            final_survey_fc = os.path.join(final_gdb_for_convenience, output_fc_name)

            # Only proceed with final processing if the feature class exists
            if arcpy.Exists(final_survey_fc):
                # Recalculate feature class extent for optimal performance
                arcpy.AddMessage(
                    "Step 13: Recalculating feature class extent and performing final optimization..."
                )
                try:
                    # Force cleanup before recalculating extent
                    self._cleanup_workspace(final_gdb_for_convenience)
                    time.sleep(1)

                    # Recalculate extent
                    arcpy.management.RecalculateFeatureClassExtent(final_survey_fc)

                    # Compact the geodatabase to optimize and remove temporary artifacts
                    arcpy.management.Compact(final_gdb_for_convenience)

                    # Final validation check
                    if self._validate_objectid_integrity(final_survey_fc):
                        arcpy.AddMessage(
                            "Final validation successful - output ObjectIDs preserved correctly"
                        )
                    else:
                        arcpy.AddWarning(
                            "ObjectID validation warning - check output data carefully"
                        )
                except Exception as e:
                    arcpy.AddWarning(f"Warning during final optimization: {str(e)}")
                    # Continue instead of failing - the data may still be usable

            # Output summary
            arcpy.AddMessage("=" * 60)
            arcpy.AddMessage("Survey data processing completed!")
            arcpy.AddMessage("OUTPUTS CREATED:")
            arcpy.AddMessage(f"1. ORIGINAL PACKAGE: {extract_dir}")
            arcpy.AddMessage(f"2. PROCESSED PACKAGE: {final_pkg_dir}")
            if arcpy.Exists(final_gdb_for_convenience):
                arcpy.AddMessage(f"3. CONVENIENCE GDB: {final_gdb_for_convenience}")
            arcpy.AddMessage("=" * 60)

            # Important: Set the output parameter to the final feature class
            if arcpy.Exists(final_survey_fc):
                arcpy.SetParameter(6, final_survey_fc)
                arcpy.AddMessage(f"Primary output feature class: {final_survey_fc}")
            else:
                # Fallback to the feature class in the package if convenience GDB failed
                pkg_fc = os.path.join(
                    final_pkg_dir, "commondata", "featureserver.gdb", candidate_fcs[0]
                )
                if arcpy.Exists(pkg_fc):
                    arcpy.SetParameter(6, pkg_fc)
                    arcpy.AddMessage(
                        f"Primary output feature class (in package): {pkg_fc}"
                    )

        except Exception as e:
            arcpy.AddError(f"Error in survey processing: {str(e)}")
            raise

        finally:
            # Always clean up, regardless of success or failure
            try:
                # Try to clean up with gdb path if available
                if "source_gdb" in locals():
                    self._cleanup_workspace(source_gdb)
                else:
                    self._cleanup_workspace()
            except:
                self._cleanup_workspace()  # Fallback cleanup without gdb path

            # Clean up temporary files
            try:
                if "lpkx_path" in locals() and os.path.exists(lpkx_path):
                    os.remove(lpkx_path)
            except Exception as e:
                arcpy.AddWarning(f"Warning cleaning up temporary files: {str(e)}")

            # Note: Timestamped scratch files ensure no conflicts between runs

        return
