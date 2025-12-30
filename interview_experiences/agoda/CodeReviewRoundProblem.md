## Snippet for the code (was given in .net)

The goal was to identify in which situations the avg temprature can come above 10 and below 10 for 100s input from iot devices 


```java
public class AgodaCodeReviewRound {

    private float tempReading;
    private int readingCount;

    public void updateReading (float x) {
        tempReading = tempReading + x;
        readingCount++;
    }

    public float getAvgTemprature () {
        return tempReading/readingCount;
    }
}
```