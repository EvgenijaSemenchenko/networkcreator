import os
from qgis.PyQt import uic, QtWidgets
from qgis.core import (
    QgsProject, QgsMapLayer, QgsFeature, QgsGeometry, QgsPoint, QgsVectorLayer, 
    QgsSpatialIndex, QgsField, QgsFeatureRequest, QgsLineSymbol
)
from PyQt5.QtCore import QVariant
from qgis.gui import QgsMessageBar

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'networkcreate_dialog_base.ui'))

class networkcreateDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(networkcreateDialog, self).__init__(parent)
        self.setupUi(self)
        
        # Populate the combo boxes with vector layers
        self.populate_layer_comboboxes()
        
        # Connect the Run button to its handler
        self.runButton.clicked.connect(self.create_lines_to_nearest_road)

        # Connect the Simultaneity Factor button to its handler
        self.simultaneityFactorButton.clicked.connect(self.calculate_simultaneity_factor)

        # Connect the Cumulative Peak Load button to its handler
        self.pushCumulativeButton.clicked.connect(self.calculate_load_at_node)

        # Connect the Mass Flow button to its handler
        self.pushMassflowButton.clicked.connect(self.calculate_mass_flow)

    # Your existing methods...

    def calculate_simultaneity_factor(self):
        try:
            N = float(self.numHousesLineEdit.text())
            D = 0.62
            result = D + (1 - D) / N
            self.simultaneityFactorLineEdit.setText(f"{result:.4f}")
        except ValueError:
            self.iface.messageBar().pushMessage("Error", "Please enter a valid number for houses", level=Qgis.Critical)

    def calculate_load_at_node(self):
        try:
            simultaneity_factor = float(self.simultaneityFactorLineEdit.text())
            cumulative_peak_load = float(self.cumulativePeakLoadLineEdit.text())
            load_at_node = simultaneity_factor * cumulative_peak_load
            self.loadAtNodeLineEdit.setText(f"{load_at_node:.4f}")
        except ValueError:
            self.iface.messageBar().pushMessage("Error", "Please enter valid numbers for simultaneity factor and cumulative peak load", level=Qgis.Critical)

    def calculate_mass_flow(self):
        try:
            q = float(self.cumulativePeakLoadLineEdit.text())  # in watts (W) or joules per second (J/s)
            cp = 4.186  # specific heat capacity in J/(kg*K)
            t = 51  # temperature difference in K
            mass_flow = q / (cp * t)  # result will be in kg/s
            self.massFlowLineEdit.setText(f"{mass_flow:.4f} kg/s")
        except ValueError:
            self.iface.messageBar().pushMessage("Error", "Please enter a valid number for cumulative peak load", level=Qgis.Critical)



    def populate_layer_comboboxes(self):
        # Get the list of vector layers
        layers = [layer for layer in QgsProject.instance().mapLayers().values() if layer.type() == QgsMapLayer.VectorLayer]
        
        # Clear any existing items in the combo boxes
        self.roadsComboBox.clear()
        self.buildingsComboBox.clear()
        
        # Add layer names to combo boxes
        for layer in layers:
            self.roadsComboBox.addItem(layer.name(), layer)
            self.buildingsComboBox.addItem(layer.name(), layer)

    def create_lines_to_nearest_road(self):
        # Get selected layers
        roads_layer = self.roadsComboBox.currentData()
        buildings_layer = self.buildingsComboBox.currentData()

        if not roads_layer or not buildings_layer:
            self.iface.messageBar().pushMessage("Error", "Please select valid roads and buildings layers", level=Qgis.Critical)
            return

        # Create a new memory layer to store the lines
        crs = buildings_layer.crs().toWkt()
        lines_layer = QgsVectorLayer(f'LineString?crs={crs}', 'Lines from Buildings to Roads', 'memory')
        lines_provider = lines_layer.dataProvider()
        lines_provider.addAttributes([QgsField("BuildingID", QVariant.Int), QgsField("RoadID", QVariant.Int)])
        lines_layer.updateFields()

        # Create spatial index for the roads layer
        
        index = QgsSpatialIndex(flags = QgsSpatialIndex.FlagStoreFeatureGeometries)
        for road_feat in roads_layer.getFeatures():
            index.insertFeature(road_feat)

        # Create lines from each building to the nearest road
        for building_feat in buildings_layer.getFeatures():
            building_point = building_feat.geometry().asPoint()
            print("Building point {building_point} ".format(building_point = building_point))
            nearest_ids = index.nearestNeighbor(building_point, 1)
            print("Nearest ids {nearest_ids} ".format(nearest_ids = nearest_ids))
            if nearest_ids:
                nearest_road_feat = next(roads_layer.getFeatures(QgsFeatureRequest().setFilterFid(nearest_ids[0])))
                nearest_road_geom = nearest_road_feat.geometry()
                nearest_point = nearest_road_geom.closestSegmentWithContext(building_point)[1]

                # Create a line from the building to the nearest road
                line_geom = QgsGeometry.fromPolyline([QgsPoint(building_point), QgsPoint(nearest_point)])
                line_feat = QgsFeature()
                line_feat.setGeometry(line_geom)
                line_feat.setAttributes([building_feat.id(), nearest_road_feat.id()])
                lines_provider.addFeature(line_feat)

        # Add the lines layer to the project
        QgsProject.instance().addMapLayer(lines_layer)

        # Style the lines for better visualization
        self.style_lines_layer(lines_layer)

    def style_lines_layer(self, layer):
        """Styles the lines layer for better visualization."""
        symbol = QgsLineSymbol.createSimple({'color': 'red', 'width': '0.5'})
        renderer = layer.renderer()
        renderer.setSymbol(symbol)
        layer.triggerRepaint()


