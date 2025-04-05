google.charts.load("current", { packages: ["corechart"] });

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


// to view the chartsssssssss
document.getElementById("view-charts").addEventListener("click", () => {
    document.getElementById("chart-container").style.display = "block";
    fetchDataAndDrawCharts();
});

// draw em
function fetchDataAndDrawCharts() {
    fetch("/data")
    .then(response => {
        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
        return response.json();
    })
    .then(data => {
        console.log("Chart Data Received: ", data); // Debugging
        drawModeChart(data);
        updateTrend("year");
    })
    .catch(error => console.error("Data Fetch Error:", error));

}

// based on mode of transport
function drawModeChart(data) {
    const modeData = new google.visualization.DataTable();
    modeData.addColumn("string", "Transport Mode");
    modeData.addColumn("number", "Total Emissions (kg CO₂)");

    const emissionsByMode = {};
    data.forEach(item => {
        emissionsByMode[item.transport_mode] = (emissionsByMode[item.transport_mode] || 0) + item.emission;
    });

    for (let mode in emissionsByMode) {
        modeData.addRow([mode, emissionsByMode[mode]]);
    }

    const options = { title: "CO₂ Emissions by Transport Mode" };
    const chart = new google.visualization.ColumnChart(document.getElementById("mode-chart"));
    chart.draw(modeData, options);
}

// graph for wmission over time (come back to this and fix bish)
// Update the emissions trend chart
function updateTrend(period) {
    fetch("/data")
        .then(response => response.json())
        .then(data => {
            // Parse and filter data
            const filteredData = filterByPeriod(data, period);

            // Set up chart structure
            const trendData = new google.visualization.DataTable();
            trendData.addColumn("date", "Date");
            const modes = ["road", "rail", "air", "sea"];
            modes.forEach(mode => trendData.addColumn("number", mode));

            // Aggregate emissions by date and mode
            const groupedData = {};

            filteredData.forEach(item => {
                // Ensure date consistency (strip time part)
                const dateKey = item.timestamp.split("T")[0];
                if (!groupedData[dateKey]) {
                    groupedData[dateKey] = { road: 0, rail: 0, air: 0, sea: 0 };
                }
                groupedData[dateKey][item.transport_mode] += item.emission;
            });

            // Populate chart rows
            for (const dateKey in groupedData) {
                const [year, month, day] = dateKey.split("-").map(Number);
                trendData.addRow([
                    new Date(year, month - 1, day), // Proper date object
                    groupedData[dateKey].road,
                    groupedData[dateKey].rail,
                    groupedData[dateKey].air,
                    groupedData[dateKey].sea
                ]);
            }

            // Chart options and rendering
            const options = {
                title: `Emissions Over Time (${period})`,
                curveType: "function",
                legend: { position: "bottom" },
                hAxis: { title: "Date" },
                vAxis: { title: "Emissions (kg CO₂)" },
            };

            const chart = new google.visualization.LineChart(document.getElementById("trend-chart"));
            chart.draw(trendData, options);
        })
        .catch(error => console.error("Error loading trend chart:", error));
}


// filtering by prd
// Filter emissions by the selected time period
function filterByPeriod(data, period) {
    const now = new Date();
    return data.filter(item => {
        const itemDate = new Date(item.timestamp);
        
        switch (period) {
            case "day":
                return (now - itemDate) <= 24 * 60 * 60 * 1000; // 1 day
            case "month":
                return (now - itemDate) <= 30 * 24 * 60 * 60 * 1000; // ~1 month
            case "year":
                return (now - itemDate) <= 365 * 24 * 60 * 60 * 1000; // ~1 year
            default:
                return true;
        }
    });
}

