# Build from spring_ai_service/ :  docker build -t semiconductor-spring-ai spring_ai_service
FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /src
COPY pom.xml .
RUN mvn -B -q dependency:go-offline
COPY src ./src
# Tests run in CI (they read ../shared/redaction_cases.json, which is outside this build context).
ARG MAVEN_PROFILE=
RUN mvn -B -q package -DskipTests ${MAVEN_PROFILE:+-P$MAVEN_PROFILE}

FROM eclipse-temurin:17-jre
RUN useradd -m app
USER app
COPY --from=build /src/target/spring-ai-service-0.1.0.jar /app/app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
