// Load Google Charts
google.charts.load("current", { packages: ["corechart"] });

// Submit Emission Form
document.getElementById("emissionForm").addEventListener("submit", async function (e) {
    e.preventDefault();

    const formData = new FormData(this);
    try {
        const response = await fetch("/emissions", { method: "POST", body: formData });

        if (!response.ok) {
            const errorData = await response.json();
            alert("Error: " + (errorData.error || "Unknown error"));
            return;
        }

        const data = await response.json();
        alert(`Emission Recorded: ${data.emission.toFixed(2)} g CO₂`);
    } catch (error) {
        alert("Network Error: " + error.message);
    }
});

// View Charts Button
document.getElementById("view-charts").addEventListener("click", () => {
    document.getElementById("chart-container").style.display = "block";
    fetchDataAndDrawCharts();
});

// Fetch and Draw All Charts
function fetchDataAndDrawCharts() {
    fetch("/data")
        .then(response => {
            if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
            return response.json();
        })
        .then(data => {
            console.log("Chart Data Received: ", data);
            drawModeChart(data);
            updateTrend("year"); // default to "year"
        })
        .catch(error => console.error("Data Fetch Error:", error));
}

// Bar Chart: Emissions by Transport Mode
function drawModeChart(data) {
    const modeData = new google.visualization.DataTable();
    modeData.addColumn("string", "Transport Mode");
    modeData.addColumn("number", "Total Emissions (kg CO₂)");

    const emissionsByMode = {};
    data.forEach(item => {
        const safeEmission = Math.max(0, item.emission); // Prevent negative values
        emissionsByMode[item.transport_mode] = (emissionsByMode[item.transport_mode] || 0) + safeEmission;
    });

    for (let mode in emissionsByMode) {
        modeData.addRow([mode, emissionsByMode[mode]]);
    }

    const options = {
        title: "CO₂ Emissions by Transport Mode",
        hAxis: { title: "Mode" },
        vAxis: { title: "Emissions (kg CO₂)" }
    };

    const chart = new google.visualization.ColumnChart(document.getElementById("mode-chart"));
    chart.draw(modeData, options);
}

// Line Chart: Emissions Over Time
function updateTrend(period) {
    fetch("/data")
        .then(response => response.json())
        .then(data => {
            const filteredData = filterByPeriod(data, period);

            const trendData = new google.visualization.DataTable();
            trendData.addColumn("date", "Date");
            const modes = ["road", "rail", "air", "sea"];
            modes.forEach(mode => trendData.addColumn("number", mode));

            const groupedData = {};
            filteredData.forEach(item => {
                const dateKey = item.timestamp.split("T")[0];
                const safeEmission = Math.max(0, item.emission); // Clamp to zero

                if (!groupedData[dateKey]) {
                    groupedData[dateKey] = { road: 0, rail: 0, air: 0, sea: 0 };
                }

                groupedData[dateKey][item.transport_mode] += safeEmission;
            });

            // Convert to sorted chart rows
            const chartRows = [];

            for (const dateKey in groupedData) {
                const [year, month, day] = dateKey.split("-").map(Number);
                chartRows.push([
                    new Date(year, month - 1, day),
                    groupedData[dateKey].road,
                    groupedData[dateKey].rail,
                    groupedData[dateKey].air,
                    groupedData[dateKey].sea
                ]);
            }

            chartRows.sort((a, b) => a[0] - b[0]); // Sort by date
            chartRows.forEach(row => trendData.addRow(row));

            const options = {
                title: `Emissions Over Time (${period})`,
                curveType: "function",
                legend: { position: "bottom" },
                hAxis: { title: "Date" },
                vAxis: { title: "Emissions (kg CO₂)" },
                explorer: { actions: ["dragToZoom", "rightClickToReset"] }
            };

            const chart = new google.visualization.LineChart(document.getElementById("trend-chart"));
            chart.draw(trendData, options);
        })
        .catch(error => console.error("Error loading trend chart:", error));
}

// Time Period Filtering
function filterByPeriod(data, period) {
    const now = new Date();
    return data.filter(item => {
        const itemDate = new Date(item.timestamp);

        switch (period) {
            case "day":
                return (now - itemDate) <= 24 * 60 * 60 * 1000;
            case "month":
                return (now - itemDate) <= 30 * 24 * 60 * 60 * 1000;
            case "year":
                return (now - itemDate) <= 365 * 24 * 60 * 60 * 1000;
            default:
                return true;
        }
    });
}
